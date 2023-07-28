import uuid
from enum import Enum
from typing import List, TypedDict

from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import ARRAY

from main.app import db


class PaginatedItemDict(TypedDict):
    items: List
    _meta: dict
    _links: dict


class StatusOption(Enum):
    INPROCESS = "in_process"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"


class EventType(Enum):
    STATUS_CHANGED = 'status_changed'
    RESOURCE_ADDED = 'resource_added'
    RESOURCE_DELETED = 'resource_deleted'
    PHOTO_ADDED = "photo_added"


class WebResource(db.Model):
    """Model for urls."""
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)
    full_url = db.Column(db.String, nullable=False, unique=True, index=True)
    protocol = db.Column(db.String, nullable=False)
    domain = db.Column(db.String, nullable=False)
    domain_zone = db.Column(db.String, nullable=False, index=True)
    url_path = db.Column(db.String)
    query_params = db.Column(JSON)
    unavailable_count = db.Column(db.Integer, default=0)
    screenshot = db.Column(db.LargeBinary, nullable=True)
    status_codes = relationship("WebResourceStatus", back_populates="resource")
    news_feed_items = relationship("NewsFeedItem", back_populates="resource")


class WebResourceStatus(db.Model):
    """Model for statuses of Web resources."""
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey(WebResource.id))
    status_code = db.Column(db.Integer, nullable=True)
    request_time = db.Column(db.DateTime(timezone=True), server_default=func.now())
    is_available = db.Column(db.Boolean)
    resource = relationship("WebResource", back_populates="status_codes", lazy="joined")


class FileProcessingRequest(db.Model):
    """Model for requests for processing URLs from file. Tracked by Celery."""
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(StatusOption), default=StatusOption.PENDING, nullable=False)
    task_id = db.Column(db.String, index=True, nullable=True)
    total_count = db.Column(db.Integer, nullable=True, default=None)
    processed_count = db.Column(db.Integer, nullable=True, default=None)
    errors_count = db.Column(db.Integer, nullable=True, default=None)
    error_urls = db.Column(ARRAY(db.String), default=[])


class NewsFeedItem(db.Model):
    """Model for news feed items."""
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.Enum(EventType), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey(WebResource.id))
    resource = relationship("WebResource", back_populates="news_feed_items")
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
