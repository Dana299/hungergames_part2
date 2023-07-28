from base64 import b64encode
from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, AnyHttpUrl, BaseModel, root_validator, validator
from werkzeug.datastructures import FileStorage


class ResourceCreateRequestSchema(BaseModel):
    url: AnyHttpUrl


class ResourceCreateResponseSchema(BaseModel):
    uuid: UUID4
    protocol: str
    domain: str
    domain_zone: str
    url_path: Optional[str]
    full_url: str
    query_params: Optional[dict]


class ListResourceGetSchemaItem(ResourceCreateResponseSchema):
    id: int
    status_code: Optional[int]
    is_available: Optional[bool]


class ResourceGetSchema(ListResourceGetSchemaItem):
    screenshot: Optional[str]

    @root_validator(pre=True)
    def convert_bytes_to_base64(cls, values):
        screenshot = values.get("screenshot")
        if screenshot is not None and isinstance(screenshot, bytes):
            values["screenshot"] = b64encode(screenshot).decode("utf-8")
        return values


class ListResourceGetSchema(BaseModel):
    items: List[ListResourceGetSchemaItem]


class PaginatedResourceListSchema(ListResourceGetSchema):
    meta: dict
    links: dict


class FileRequestSchema(BaseModel):
    file: FileStorage

    @validator('file')
    def validate_file(cls, file):
        if file is None or file.filename == '':
            raise ValueError('File cannot be empty')
        return file

    class Config:
        arbitrary_types_allowed = True


class ZipFileRequestSchema(FileRequestSchema):
    @validator('file')
    def validate_file(cls, file):
        if file is None or file.filename == '':
            raise ValueError('File cannot be empty')

        if not file.filename.lower().endswith('.zip'):
            raise ValueError('Invalid file type. Only ZIP files are allowed.')

        return file


class NewsFeedItemSchema(BaseModel):
    event_type: str
    timestamp: datetime


class ResourcePageSchema(ResourceGetSchema):
    events: List[NewsFeedItemSchema]
