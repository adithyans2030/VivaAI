"""Subject Schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentResponse


class SubjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    description: str = Field(default="", max_length=2000)


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=2000)


class SubjectResponse(SubjectBase):
    id: str
    teacher_id: str
    created_at: datetime
    updated_at: datetime
    document_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class SubjectDetailResponse(SubjectResponse):
    documents: List[DocumentResponse] = []

    model_config = ConfigDict(from_attributes=True)
