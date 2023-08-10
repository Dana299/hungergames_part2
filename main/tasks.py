import json
import os
from typing import List, Optional, TypedDict

import requests
from celery import current_task, shared_task
from pydantic import ValidationError
from redis import Redis

from main import app
from main.db import schemas
from main.db.models import EventType, StatusOption
from main.service import db, exceptions
from main.utils import ziploader


class FileProcessingErrorsDict(TypedDict):
    """Class that represent `errors` field in result of file processing."""
    count: int
    error_urls: Optional[List[str]]


class FileProcessingTaskResponse(TypedDict):
    """Class that represens result of file processing."""
    status: str
    total: int
    processed: int
    errors: FileProcessingErrorsDict


@shared_task
def get_response_from_resources():
    """Get all urls from DB, make requests and write response status codes to DB."""

    # for future: distribute all urls between multiple celery workers.

    resources_from_db = db.get_web_resources_query().all()

    for resource in resources_from_db:

        last_availability = resource.status_codes[-1].is_available if resource.status_codes else None

        try:
            response = requests.get(resource.full_url)
            status_code = response.status_code
            is_available = True if status_code in range(200, 400) else False

        except requests.RequestException:
            is_available = False
            status_code = 404

        finally:
            db.update_counter_for_resource_availability(
                resource=resource,
                is_available=is_available
            )
            db.save_status_code_for_web_resource_response(
                resource=resource,
                status_code=response.status_code,
                is_available=is_available,
            )

            # add newsfeed item if status has changed from the last time
            if last_availability != is_available:
                db.create_newsfeed_item(
                    resource=resource,
                    event=EventType.STATUS_CHANGED,
                )


@shared_task
def delete_unavailable_resources(unavailable_count: int):
    unavailable_resources = db.get_web_resources_query(
        unavailable_count=unavailable_count,
    )

    for resource in unavailable_resources:
        db.delete_web_resource(resource=resource)


@shared_task
def process_urls_from_zip_archive(zip_file: str, request_id: int):
    """
    Celery task that processes urls from the file.
    This task iterates over the lines of the file and writes the result in redis on each step.
    At the end of processing it saves the final result in DB.
    """

    # get celery task ID
    task_id = current_task.request.id

    processing_request = db.get_file_processing_request_by_id(request_id=request_id)

    try:

        # TODO: move to separate function

        lines_from_csv = ziploader.get_lines_from_csv(
            zip_file=os.path.join(app.config["UPLOAD_FOLDER"], zip_file)
        )

        # initialize counters
        total_lines_number = len(lines_from_csv)
        processed_count = 0
        errors_count = 0
        error_urls = []

        validated_urls: List[str] = []

        redis_client: Redis = app.extensions["redis"]

        # put initial processing result with zeros in redis
        task_response: FileProcessingTaskResponse = {
            "status": StatusOption.INPROCESS.value,
            "total": total_lines_number,
            "processed": processed_count,
            "errors": {
                "count": errors_count,
                "error_urls": error_urls
            }
        }

        task_response_json = json.dumps(task_response)
        redis_client.set(name=task_id, value=task_response_json)

        db.update_processing_request(
            processing_request=processing_request,
            status=StatusOption.INPROCESS,
            task_id=task_id,
        )

        for line in lines_from_csv:

            try:
                # try to validate url and add it to list with valid urls for further bulk create in db
                validated_url = schemas.ResourceCreateRequestSchema.parse_obj({"url": line})
                validated_urls.append(validated_url.url)

            except ValidationError:
                # increment counter is URL is invalid
                errors_count += 1
                error_urls.append(line)

            finally:
                processed_count += 1

            # update fields in response for redis
            task_response["processed"] = processed_count
            task_response["errors"]["count"] = errors_count
            task_response["errors"]["error_urls"] = error_urls

            # сonvert task response dictionary to JSON
            task_response_json = json.dumps(task_response)

            # set task response JSON in Redis
            redis_client.set(name=task_id, value=task_response_json)

        db.bulk_create_web_resources(validated_urls=validated_urls)

        db.update_processing_request(
            processing_request=processing_request,
            total_count=total_lines_number,
            processed_count=processed_count,
            errors_count=errors_count,
            error_urls=error_urls,
            status=StatusOption.SUCCEEDED,
        )

    except exceptions.NoCSVFileError:
        # this log will be sent to celery, not to app
        # TODO: change this behaviour
        app.logger.info("Celery task failed cause ZIP archive did not contain any CSV file.")
        db.update_processing_request(
            processing_request=processing_request,
            status=StatusOption.FAILED,
            task_id=task_id,
        )
