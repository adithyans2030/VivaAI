"""Subject management routes."""

from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.models.document import Document
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectDetailResponse, SubjectResponse, SubjectUpdate
from app.services.rag import get_rag_store

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=List[SubjectResponse])
async def list_subjects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> List[SubjectResponse]:
    """List available subjects."""
    stmt = (
        select(
            Subject,
            func.count(Document.id).label("doc_count"),
        )
        .outerjoin(Document, Subject.id == Document.subject_id)
        .group_by(Subject.id)
        .order_by(Subject.name)
    )
    result = await db.execute(stmt)
    subjects_with_counts = []
    for subject, doc_count in result.all():
        subj_dict = SubjectResponse.model_validate(subject)
        subj_dict.document_count = doc_count
        subjects_with_counts.append(subj_dict)

    return subjects_with_counts


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_in: SubjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Subject:
    """Create a new subject (Teacher/Admin only)."""
    # Check if code is unique
    stmt = select(Subject).where(Subject.code == subject_in.code)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject code '{subject_in.code}' already exists",
        )

    subject = Subject(
        name=subject_in.name,
        code=subject_in.code.upper(),
        description=subject_in.description,
        teacher_id=teacher.id,
    )
    db.add(subject)
    await db.flush()
    await db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectDetailResponse)
async def get_subject(
    subject_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Subject:
    """Get subject details along with documents."""
    stmt = select(Subject).where(Subject.id == subject_id).options(selectinload(Subject.documents))
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id '{subject_id}' not found",
        )
    return subject


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    subject_in: SubjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Subject:
    """Update subject information."""
    stmt = select(Subject).where(Subject.id == subject_id)
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id '{subject_id}' not found",
        )
    if teacher.role != UserRole.ADMIN and subject.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify subjects you created",
        )

    if subject_in.name is not None:
        subject.name = subject_in.name
    if subject_in.code is not None:
        subject.code = subject_in.code.upper()
    if subject_in.description is not None:
        subject.description = subject_in.description

    await db.flush()
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> None:
    """Delete a subject and its associated documents."""
    stmt = select(Subject).where(Subject.id == subject_id)
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id '{subject_id}' not found",
        )
    if teacher.role != UserRole.ADMIN and subject.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete subjects you created",
        )

    # Remove stored files and vectors; the DB cascade only removes rows.
    docs = (await db.execute(select(Document).where(Document.subject_id == subject_id))).scalars().all()
    rag = get_rag_store()
    for doc in docs:
        await rag.delete_document(subject_id, doc.id)
        Path(doc.file_path).unlink(missing_ok=True)

    await db.delete(subject)
    await db.flush()
