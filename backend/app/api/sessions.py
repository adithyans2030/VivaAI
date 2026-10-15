"""Viva Session API routes."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.models.session import AuthenticityLikelihood, SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.session import ConsentUpdate, SessionCreate, SessionDetailResponse, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_in: SessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    student: Annotated[User, Depends(get_current_user)],
) -> VivaSession:
    """Create a new viva examination session for a student."""
    # Check subject existence
    stmt = select(Subject).where(Subject.id == session_in.subject_id)
    subject = (await db.execute(stmt)).scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id '{session_in.subject_id}' not found",
        )

    session = VivaSession(
        student_id=student.id,
        subject_id=session_in.subject_id,
        status=SessionStatus.CREATED,
        recording_consent=False,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.post("/{session_id}/consent", response_model=SessionResponse)
async def update_session_consent(
    session_id: str,
    consent_in: ConsentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    student: Annotated[User, Depends(get_current_user)],
) -> VivaSession:
    """Record student's explicit consent to audio recording for the viva session."""
    stmt = select(VivaSession).where(VivaSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found",
        )

    if session.student_id != student.id and student.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only provide consent for your own examination session",
        )

    session.recording_consent = consent_in.recording_consent
    await db.flush()
    await db.refresh(session)
    return session


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    subject_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    status_filter: Optional[SessionStatus] = Query(None),
    flag_level: Optional[AuthenticityLikelihood] = Query(None),
) -> List[VivaSession]:
    """List sessions with optional filtering. Students only see their own sessions."""
    stmt = select(VivaSession).order_by(VivaSession.created_at.desc())

    if current_user.role == UserRole.STUDENT:
        stmt = stmt.where(VivaSession.student_id == current_user.id)
    elif student_id:
        stmt = stmt.where(VivaSession.student_id == student_id)

    if subject_id:
        stmt = stmt.where(VivaSession.subject_id == subject_id)
    if status_filter:
        stmt = stmt.where(VivaSession.status == status_filter)
    if flag_level:
        stmt = stmt.where(VivaSession.overall_authenticity_likelihood == flag_level)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_details(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionDetailResponse:
    """Retrieve full details of a session, including questions, audio, and rubric scores."""
    stmt = (
        select(VivaSession)
        .where(VivaSession.id == session_id)
        .options(
            selectinload(VivaSession.turns),
            selectinload(VivaSession.student),
            selectinload(VivaSession.subject),
        )
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found",
        )

    if current_user.role == UserRole.STUDENT and session.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this viva session",
        )

    detail = SessionDetailResponse.model_validate(session)
    detail.student_name = session.student.full_name if session.student else None
    detail.subject_name = session.subject.name if session.subject else None
    detail.subject_code = session.subject.code if session.subject else None
    return detail
