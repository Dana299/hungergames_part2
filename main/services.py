from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm.query import Query
from werkzeug.datastructures import FileStorage

from main.app import db
from main.db.models import (FileProcessingRequest, WebResource,
                            WebResourceStatus)
from main.utils.urlparser import parse_url


def create_web_resource(validated_url: str) -> WebResource | None:
    """Save WebResource instance in database."""
    response = parse_url(url=validated_url)

    web_resource = WebResource(
        full_url=validated_url,
        protocol=response.protocol,
        domain=response.domain,
        domain_zone=response.domain_zone,
        url_path=response.path,
        query_params=response.query_params,
    )

    # check whether resource already exists in DB
    existing_resource = WebResource.query.filter_by(full_url=validated_url).first()

    if existing_resource:
        return None

    db.session.add(web_resource)
    db.session.commit()
    return web_resource


def get_web_resources(
    domain_zone: Optional[str] = None,
    resource_id: Optional[int] = None,
    resource_uuid: Optional[str] = None,
    is_available: Optional[bool] = None,
) -> Query:
    """Get all WebResource instances from database with the given criteria."""

    # base query
    query = db.session.query(
        WebResource.id,
        WebResource.full_url,
        WebResourceStatus.status_code
    ).join(
        WebResourceStatus,
        WebResource.id == WebResourceStatus.resource_id,
        isouter=True
    ).order_by(
        WebResource.id.desc(),
        desc(WebResourceStatus.request_time)  # Сортируем по убыванию времени статуса
    ).distinct(
        WebResource.id
    )

    # applying filters to query
    if domain_zone:
        query = query.filter(WebResource.domain_zone == domain_zone)
    if resource_id:
        query = query.filter(WebResource.id == resource_id)
    if resource_uuid:
        query = query.filter(WebResource.uuid == resource_uuid)
    if is_available:
        query = query.filter(WebResourceStatus.is_available == is_available)

    return query


def delete_web_resource_by_id(resource_id: int) -> bool:
    """Get WebResource object from DB and deletes it if it was found. Return corresponding boolean flag."""
    is_deleted = False
    resource = WebResource.query.filter_by(id=resource_id).first()

    if resource:
        db.session.delete(resource)
        db.session.commit()
        is_deleted = True

    return is_deleted


def delete_web_resource(resource: WebResource):
    """Delete web resource from DB."""
    db.session.delete(resource)
    db.session.commit()


def save_status_code_for_web_resource_response(
    resource: WebResource,
    status_code: int,
    is_available: bool,
):
    """Save new record for WebResourceStatus in DB."""
    status = WebResourceStatus(
        status_code=status_code,
        resource=resource,
        is_available=is_available,
    )
    db.session.add(status)
    db.session.commit()


def update_counter_for_resource_availability(resource: WebResource, is_available: bool):
    """Increment or reset counter in WebResource model."""
    if is_available:
        resource.unavailable_count = 0
    else:
        resource.unavailable_count += 1
    db.session.add(resource)
    db.session.commit()


def get_resource_by_uuid(uuid_: int) -> WebResource:
    resource = WebResource.query.filter_by(uuid=uuid_).first()
    return resource


def add_image_to_resource(resource: WebResource, image: FileStorage):
    """Add screenshot to resource in DB."""
    resource.screenshot = image.read()
    db.session.add(resource)
    db.session.commit()


def create_file_processing_request() -> int:
    """Create FileProcessingRequest model instance in DB and returns its ID."""
    processing_request = FileProcessingRequest()
    db.session.add(processing_request)
    db.session.commit()

    return processing_request.id


def get_file_processing_request_by_id(request_id: int) -> FileProcessingRequest:
    """Find FileProcessingRequest by given ID and return it."""
    processing_request = FileProcessingRequest.query.filter_by(id=request_id).first()
    return processing_request


def extract_duplicates(urls: List[str]) -> List[str]:

    existing_resources = db.session.query(WebResource).filter(
        WebResource.full_url.in_(urls)
    ).all()

    # extract it full url field
    existing_urls = [obj.full_url for obj in existing_resources]

    # filter all urls that need to be save
    urls_to_save = [url for url in urls if url not in existing_urls]

    return urls_to_save


def bulk_create_web_resources(validated_urls: List[str]):
    """Parse and save multiple WebResource instances in the database using bulk_create."""
    web_resources = []

    urls_to_save = extract_duplicates(urls=validated_urls)

    # find in DB those WebResources instances that already exist

    for url in urls_to_save:
        parsed_url = parse_url(url=url)
        web_resource = WebResource(
            full_url=url,
            protocol=parsed_url.protocol,
            domain=parsed_url.domain,
            domain_zone=parsed_url.domain_zone,
            url_path=parsed_url.path,
            query_params=parsed_url.query_params,
        )
        web_resources.append(web_resource)

    db.session.bulk_save_objects(web_resources)
    db.session.commit()


def update_processing_request(
    processing_request: FileProcessingRequest,
    total_urls: Optional[int] = None,
    processed_urls: Optional[int] = None,
    is_finished: Optional[bool] = None,
    errors: Optional[int] = None,
):
    if total_urls is not None:
        processing_request.total_urls = total_urls

    if processed_urls is not None:
        processing_request.processed_urls = processed_urls

    if is_finished is not None:
        processing_request.is_finished = is_finished

    if errors is not None:
        processing_request.errors = errors

    db.session.add(processing_request)
    db.session.commit()
