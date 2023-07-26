import json

from pydantic import ValidationError

from main.db import schemas
from main.db.models import StatusOption
from main.service import db, exceptions
from main.tasks import (FileProcessingTaskResponse,
                        process_urls_from_zip_archive)


def handle_post_url_json(body) -> schemas.ResourceCreateResponseSchema:
    try:
        validated_url = schemas.ResourceCreateRequestSchema(**body)

    except ValidationError as e:
        raise e

    try:
        web_resource = db.create_web_resource(validated_url.url)
        url = schemas.ResourceCreateResponseSchema(
            full_url=validated_url.url,
            uuid=web_resource.uuid,
            protocol=web_resource.protocol,
            domain=web_resource.domain,
            domain_zone=web_resource.domain_zone,
            url_path=web_resource.url_path,
            query_params=web_resource.query_params,
        )
        return url

    except exceptions.AlreadyExistsError as e:
        raise e


def handle_post_url_file(files) -> int:
    try:
        validated_data = schemas.ZipFileRequestSchema(**files)

    except ValidationError as e:
        raise e

    # create ZipFileProcessingRequest model instance
    processing_request_id = db.create_file_processing_request()

    # create celery task and pass id of created request to it as argument
    process_urls_from_zip_archive.delay(
        zip_file=validated_data.file.read(),
        request_id=processing_request_id,
    )

    return processing_request_id


def handle_post_image(files, resource):
    try:
        validated_data = schemas.FileRequestSchema(**files)
        db.add_image_to_resource(resource, validated_data.file)

    except ValidationError as e:
        raise e


def handle_get_request_status(request_id, storage_client) -> FileProcessingTaskResponse:
    processing_request = db.get_file_processing_request_by_id(request_id)

    if not processing_request:
        raise exceptions.NotFoundError

    if processing_request.status == StatusOption.INPROCESS:
        task_id = processing_request.task_id
        status_info_from_storage = storage_client.get(name=task_id)

        if status_info_from_storage:
            status_info = json.loads(status_info_from_storage)
            return FileProcessingTaskResponse(**status_info)
        else:
            # TODO: unexpected case but should be handled
            ...

    else:
        status_info: FileProcessingTaskResponse = {
            "status": processing_request.status.value,
            "processed": processing_request.processed_count,
            "total": processing_request.total_count,
            "errors": {
                "count": processing_request.errors_count,
                "error_urls": processing_request.error_urls,
            }
        }

        return status_info
