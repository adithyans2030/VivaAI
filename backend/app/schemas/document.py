"""Document Schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.document import IngestionStatus


class DocumentBase(BaseModel):
    filename: str
    file_type: str
    file_size_bytes: int


class DocumentResponse(DocumentBase):
    id: str
    subject_id: str
    chunk_count: int
    ingestion_status: IngestionStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentIngestionStatusResponse(BaseModel):
    document_id: str
    status: IngestionStatus
    chunk_count: int
    error_message: Optional[str] = None
