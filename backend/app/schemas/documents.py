from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    text: str
    page: int | None
    section: str | None
    token_count: int
    content_hash: str

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    sha256: str
    version: int
    status: str
    page_count: int | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class DocumentDetailResponse(DocumentResponse):
    chunks: list[ChunkResponse]