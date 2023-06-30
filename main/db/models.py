import uuid

from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from main.app import db


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


class WebResourceStatus(db.Model):
    """Model for statuses of Web resources."""
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey(WebResource.id))
    status_code = db.Column(db.Integer, nullable=True)
    is_available = db.Column(db.Boolean)
    resource = relationship("WebResource", back_populates="status_codes", lazy="joined")


class FileProcessingRequest(db.Model):
    """Model for requests for processing URLs from file. Tracked by Celery."""
    id = db.Column(db.Integer, primary_key=True)
    total_urls = db.Column(db.Integer, nullable=True, default=None)
    processed_urls = db.Column(db.Integer, nullable=True, default=None)
    errors = db.Column(db.Integer, nullable=True, default=None)
    is_finished = db.Column(db.Boolean, default=False)
