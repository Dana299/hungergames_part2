from typing import List, NoReturn, Optional, TypedDict

from flask import url_for
from sqlalchemy import desc
from sqlalchemy.orm.query import Query
from werkzeug.datastructures import FileStorage

from main.app import db
from main.db.models import (FileProcessingRequest, NewsFeedItem, StatusOption,
                            WebResource, WebResourceStatus)
from main.service import exceptions
from main.utils.urlparser import parse_url


class PaginatedItemDict(TypedDict):
    items: List
    _meta: dict
    _links: dict


def create_web_resource(validated_url: str) -> WebResource:
    """Save WebResource instance in database. If it already exists raise AlreadyExistsError."""
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
        raise exceptions.AlreadyExistsError

    else:
        db.session.add(web_resource)
        db.session.commit()

        # TODO: fix migration that add new EventType

        # create_newsfeed_item(
        #     resource=web_resource,
        #     event=NewsFeedItem.EventType.RESOURCE_ADDED,
        # )

        return web_resource


def get_web_resources_query(
    left_join: bool = False,
    domain_zone: Optional[str] = None,
    resource_id: Optional[int] = None,
    resource_uuid: Optional[str] = None,
    is_available: Optional[bool] = None,
    unavailable_count: Optional[int] = None,
) -> Query:
    """
    Get all WebResource instances from database with the given criteria.
    If left join is True then return query with relative data (status codes).
    Else return query with all Web resources."""

    if not left_join:
        query = db.session.query(WebResource)

    else:
        # base query
        query = db.session.query(
            WebResource.id,
            WebResource.uuid,
            WebResource.full_url,
            WebResourceStatus.status_code,
            WebResourceStatus.is_available,
            WebResource.domain_zone,
            WebResource.domain,
            WebResource.screenshot,
            WebResource.protocol,
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
    if unavailable_count:
        query = query.filter(WebResource.unavailable_count >= unavailable_count)

    return query


def delete_web_resource_by_id(resource_id: int):
    """Get WebResource object from DB and deletes it if it was found. Raise exception otherwise."""
    resource = WebResource.query.filter_by(id=resource_id).first()

    if not resource:
        raise exceptions.NotFoundError

    db.session.delete(resource)
    db.session.commit()


def delete_web_resource(resource: WebResource):
    """Delete web resource from DB."""
    db.session.delete(resource)
    db.session.commit()

    create_newsfeed_item(
        resource=resource,
        event=NewsFeedItem.EventType.RESOURCE_DELETED,
    )


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


def get_resource_by_uuid(uuid_: str) -> WebResource | NoReturn:
    resource = WebResource.query.filter_by(uuid=uuid_).first()

    if not resource:
        raise exceptions.NotFoundError

    return resource


def add_image_to_resource(resource: WebResource, image: FileStorage):
    """Add screenshot to resource in DB."""
    resource.screenshot = image.read()
    db.session.add(resource)
    db.session.commit()

    # create_newsfeed_item(
    #     resource=resource,
    #     event=NewsFeedItem.EventType.PHOTO_ADDED,
    # )


def create_file_processing_request() -> int:
    """Create FileProcessingRequest model instance in DB and returns its ID."""
    processing_request = FileProcessingRequest()
    db.session.add(processing_request)
    db.session.commit()

    return processing_request.id


def get_file_processing_request_by_id(request_id: int) -> Optional[FileProcessingRequest]:
    """Find FileProcessingRequest by given ID and return it if found else return None."""
    processing_request = FileProcessingRequest.query.filter_by(id=request_id).one_or_none()
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
    task_id: Optional[str] = None,
    total_count: Optional[int] = None,
    processed_count: Optional[int] = None,
    errors_count: Optional[int] = None,
    error_urls: Optional[List[str]] = None,
    status: Optional[StatusOption] = None,
):
    """Update the given fields in the given processing request in DB."""

    if task_id is not None:
        processing_request.task_id = task_id

    if total_count is not None:
        processing_request.total_count = total_count

    if processed_count is not None:
        processing_request.processed_count = processed_count

    if errors_count is not None:
        processing_request.errors_count = errors_count

    if error_urls is not None:
        processing_request.error_urls = error_urls

    if status is not None:
        processing_request.status = status

    db.session.add(processing_request)
    db.session.commit()


def create_newsfeed_item(resource, event):
    """Create new NewsFeedItem in DB with the given event for the given resource."""

    news_item = NewsFeedItem(
        event_type=event,
        resource=resource
    )

    db.session.add(news_item)
    db.session.commit()


def get_resource_page(resource_uuid: str):
    """Get all WebResource data including related."""
    try:
        get_resource_by_uuid(resource_uuid)
    except exceptions.NotFoundError:
        raise

    # Join the News and StatusCode tables with the WebResource table
    query = db.session.query(WebResource, NewsFeedItem, WebResourceStatus).\
        join(NewsFeedItem, WebResource.id == NewsFeedItem.resource_id, isouter=True).\
        join(WebResourceStatus, WebResourceStatus.resource_id == WebResource.id, isouter=True).\
        filter(WebResource.uuid == resource_uuid)
    # Execute the query and retrieve the results
    return query.all()


def paginate_query(query, page, per_page, endpoint, **kwargs) -> PaginatedItemDict:
    items_ = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    data: PaginatedItemDict = {
        'items': [item._asdict() for item in items_.items],
        '_meta': {
            'page': page,
            'per_page': per_page,
            'total_pages': items_.pages,
            'total_items': items_.total
        },
        '_links': {
            'self': url_for(endpoint, page=page, per_page=per_page,
                            **kwargs),
            'next': url_for(endpoint, page=page + 1, per_page=per_page,
                            **kwargs) if items_.has_next else None,
            'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                            **kwargs) if items_.has_prev else None
        }
    }
    return data
