from typing import List

import requests
from celery import shared_task
from pydantic import ValidationError

from main import services
from main.db import schemas
from main.utils import ziploader


@shared_task
def get_response_from_resources():
    """Get all urls from DB, make requests and write response status codes to DB."""

    # for future: distribute all urls between multiple celery workers.

    resources_from_db = services.get_web_resources()

    for resource in resources_from_db:
        try:
            response = requests.get(resource.full_url)
            is_available = True if response.status_code in range(200, 400) else False
            services.save_status_code_for_web_resource_response(
                resource=resource,
                status_code=response.status_code,
                is_available=is_available,
            )

        except requests.RequestException:
            is_available = False
        finally:
            services.update_counter_for_resource_availability(
                resource=resource,
                is_available=is_available
            )


@shared_task
def delete_unavailable_resources(times_unavailable: int):
    unavailable_resources = services.get_web_resources(times_unavailable=times_unavailable)

    for resource in unavailable_resources:
        services.delete_web_resource(resource=resource)


@shared_task
def process_urls_from_zip_archive(zip_file: bytes, request_id: int):
    lines_from_csv = ziploader.get_lines_from_csv(zip_file=zip_file)

    processing_request = services.get_file_processing_request_by_id(request_id=request_id)

    # initialize counters
    total_lines_number = len(lines_from_csv)
    processed_urls = 0
    errors = 0

    services.update_processing_request(
        processing_request=processing_request,
        total_urls=total_lines_number,
    )

    validated_urls: List[str] = []

    for line in lines_from_csv:

        try:
            # try to validate url and add it to list with valid urls for further bulk create in db
            validated_url = schemas.RequestSchema.parse_obj({"url": line})
            validated_urls.append(validated_url.url)
            processed_urls += 1

        except ValidationError:
            # increment counter is URL is invalid
            errors += 1

    services.update_processing_request(
        processing_request=processing_request,
        errors=total_lines_number - processed_urls,
    )

    services.bulk_create_web_resources(validated_urls=validated_urls)

    services.update_processing_request(
        processing_request=processing_request,
        processed_urls=processed_urls,
        is_finished=True
    )