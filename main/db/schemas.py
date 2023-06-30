from typing import List

from pydantic import UUID4, AnyHttpUrl, BaseModel, validator
from werkzeug.datastructures import FileStorage


class RequestSchema(BaseModel):
    url: AnyHttpUrl


class ResponseSchema(BaseModel):
    uuid: UUID4
    protocol: str
    domain: str
    domain_zone: str
    url_path: str
    query_params: dict | None


class ListResponseSchema(BaseModel):
    urls: List[ResponseSchema]


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
