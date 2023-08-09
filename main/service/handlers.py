import json
import os
from typing import Optional

from pydantic import ValidationError
from werkzeug.datastructures.structures import ImmutableMultiDict

from main import app
from main.db import models, schemas
from main.service import db, exceptions
from main.tasks import (FileProcessingTaskResponse,
                        process_urls_from_zip_archive)
from main.utils import ziploader


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

    if not ziploader.allowed_file(validated_data.file.filename):
        raise exceptions.InvalidFileFormatError("File format is not in allowed extensions.")

    else:
        filename = ziploader.make_uuid_filename(validated_data.file.filename)
        validated_data.file.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename,
            )
        )

    # create ZipFileProcessingRequest model instance
    processing_request_id = db.create_file_processing_request()

    # create celery task and pass id of created request to it as argument
    process_urls_from_zip_archive.delay(
        zip_file=filename,
        request_id=processing_request_id,
    )

    return processing_request_id


def handle_add_image_for_web_resource(files: ImmutableMultiDict, resource_uuid: str) -> None:
    try:
        web_resource = db.get_resource_by_uuid(resource_uuid)
        validated_data = schemas.FileRequestSchema(**files)
        db.add_image_to_resource(web_resource, validated_data.file)

    except exceptions.NotFoundError:
        raise

    except ValidationError as e:
        raise e


def handle_get_request_status(request_id, storage_client) -> FileProcessingTaskResponse:
    processing_request = db.get_file_processing_request_by_id(request_id)

    if not processing_request:
        raise exceptions.NotFoundError

    if processing_request.status == models.StatusOption.INPROCESS:
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


def handle_get_resources_with_filters(
    domain_zone: Optional[str],
    availability: Optional[str],
    resource_id: Optional[int],
    uuid: Optional[str],
    page: Optional[int],
    per_page: Optional[int],
) -> schemas.PaginatedResourceListSchema:

    query = db.get_web_resources_query(
        left_join=True,
        domain_zone=domain_zone,
        resource_id=resource_id,
        resource_uuid=uuid,
        is_available=availability,
    )

    paginated_resource_list = db.paginate_query(
        query,
        page,
        per_page,
        'main.get_resources',
    )

    paginated_resources_with_meta_data = schemas.PaginatedResourceListSchema(
        items=[
            schemas.ResourceGetSchema(**item).dict() for item in paginated_resource_list["items"]
        ],
        meta=paginated_resource_list.get('_meta'),
        links=paginated_resource_list.get('_links')
    )

    return paginated_resources_with_meta_data


def handle_get_resource_data(resource_uuid: str) -> schemas.ResourcePageSchema:

    # TODO: refactor!!!

    try:
        page = db.get_resource_page(resource_uuid=resource_uuid)
        resource: models.WebResource = page[0][0]   # WebResource is on the 1 position in tuple
        events = []

        for item in page:
            news_item: models.NewsFeedItem = item[1]  # NewsFeedItem is on the 2 position in tuple
            if news_item:
                news_dict = {
                    "event_type": news_item.event_type.value,
                    "timestamp": news_item.timestamp.isoformat()
                }
                events.append(news_dict)

        resource_page = schemas.ResourcePageSchema(
            **resource.__dict__, events=events,
        )

        return resource_page

    except exceptions.NotFoundError:
        raise


def handle_get_news_feed() -> schemas.NewsFeedSchema:
    """Handle request for getting all news feed items."""
    news_items_from_db = db.get_news_items()
    feed_items = [
        schemas.NewsFeedItemWithWebResourceSchema(
            event_type=item.event_type.value,
            timestamp=item.timestamp,
            web_resource=schemas.ResourceBaseSchema(
                **item.resource.__dict__
            )
        )
        for item in news_items_from_db
    ]

    return schemas.NewsFeedSchema(feed_items=feed_items)
