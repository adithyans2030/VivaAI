"""Document management and file upload routes."""

import shutil
from pathlib import Path
from typing import Annotated, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document, IngestionStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.document import DocumentIngestionStatusResponse, DocumentResponse

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@router.get("/subjects/{subject_id}/documents", response_model=List[DocumentResponse])
async def list_subject_documents(
    subject_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> List[Document]:
    """List all documents for a specific subject."""
    stmt = (
        select(Document)
        .where(Document.subject_id == subject_id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/subjects/{subject_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    subject_id: str,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Document:
    """Upload a study document (PDF, DOCX, TXT, MD) to a subject's knowledge base."""
    stmt = select(Subject).where(Subject.id == subject_id)
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id '{subject_id}' not found",
        )

    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Prepare subject-specific directory
    subject_dir = settings.DOCUMENT_STORAGE_PATH / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    saved_path = subject_dir / unique_filename

    # Save file contents
    file_size = 0
    with open(saved_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                saved_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)}MB",
                )
            buffer.write(chunk)

    document = Document(
        subject_id=subject_id,
        filename=file.filename or unique_filename,
        file_path=str(saved_path),
        file_type=file_ext.lstrip("."),
        file_size_bytes=file_size,
        chunk_count=0,
        ingestion_status=IngestionStatus.PENDING,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    # Trigger background ingestion
    from app.services.rag import ingest_document_pipeline
    import asyncio
    asyncio.create_task(ingest_document_pipeline(document.id))

    return document


@router.get("/documents/{document_id}/status", response_model=DocumentIngestionStatusResponse)
async def get_document_status(
    document_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentIngestionStatusResponse:
    """Get the current ingestion status and chunk count of an uploaded document."""
    stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    return DocumentIngestionStatusResponse(
        document_id=doc.id,
        status=doc.ingestion_status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> None:
    """Delete a document and its stored file."""
    stmt = select(Document).where(Document.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # Remove physical file
    Path(doc.file_path).unlink(missing_ok=True)

    await db.delete(doc)
    await db.flush()
