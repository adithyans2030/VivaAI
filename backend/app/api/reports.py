"""Teacher reports, grade overrides, and audit trails."""

import asyncio
import csv
import io
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ensure_session_access, get_current_user, require_role
from app.core.database import get_db
from app.models.audit import AuditLog, ScoreOverride
from app.models.session import VivaSession
from app.models.turn import Turn
from app.models.user import User, UserRole
from app.schemas.report import (
    SessionReport,
    TeacherNoteUpdate,
    TeacherOverrideRequest,
)
from app.schemas.turn import TurnResponse
from app.services.report_pdf import build_session_pdf

router = APIRouter(prefix="/reports", tags=["reports"])

ADVISORY_EXPORT_NOTE = (
    "Authenticity columns are ADVISORY ONLY: indicators to prompt a conversation with the student, "
    "not evidence of misconduct. They never change scores. See docs/authenticity-methodology.md for limitations."
)


@router.get("/sessions/{session_id}", response_model=SessionReport)
async def get_session_report(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionReport:
    """Get the comprehensive viva report for a session."""
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
    await ensure_session_access(db, current_user, session)

    if current_user.role == UserRole.STUDENT and session.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this viva report",
        )

    return SessionReport(
        session_id=session.id,
        subject_id=session.subject_id,
        subject_name=session.subject.name if session.subject else "Unknown",
        student_id=session.student_id,
        student_name=session.student.full_name if session.student else "Unknown",
        date=session.created_at,
        total_score=session.total_score,
        authenticity_likelihood=session.overall_authenticity_likelihood,
        authenticity_confidence=session.overall_authenticity_confidence,
        authenticity_reasons=session.overall_authenticity_reasons or [],
        teacher_notes=session.teacher_notes,
        turns=[TurnResponse.model_validate(t) for t in session.turns],
        analytics=session.final_report or {},
    )


@router.post("/sessions/{session_id}/notes")
async def update_teacher_notes(
    session_id: str,
    payload: TeacherNoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Dict[str, str]:
    """Add or update teacher advisory notes for a viva session."""
    stmt = select(VivaSession).where(VivaSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found",
        )
    await ensure_session_access(db, teacher, session)

    prev_notes = session.teacher_notes
    session.teacher_notes = payload.teacher_notes

    # Add audit log
    audit = AuditLog(
        user_id=teacher.id,
        action="UPDATE_TEACHER_NOTES",
        entity_type="viva_session",
        entity_id=session.id,
        previous_state={"teacher_notes": prev_notes},
        new_state={"teacher_notes": payload.teacher_notes},
    )
    db.add(audit)
    await db.flush()

    return {"message": "Teacher notes updated successfully"}


@router.post("/sessions/{session_id}/override")
async def override_score_or_flag(
    session_id: str,
    payload: TeacherOverrideRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Dict[str, Any]:
    """Teacher override for a turn score or authenticity flag with audit recording."""
    stmt = select(VivaSession).where(VivaSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found",
        )
    await ensure_session_access(db, teacher, session)

    original_score = session.total_score or 0.0
    original_flag = session.overall_authenticity_likelihood.value

    if payload.turn_id:
        turn_stmt = select(Turn).where(Turn.id == payload.turn_id, Turn.session_id == session_id)
        turn = (await db.execute(turn_stmt)).scalar_one_or_none()
        if not turn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Turn '{payload.turn_id}' not found in session",
            )
        original_score = turn.score_0_10 or 0.0
        original_flag = turn.authenticity_likelihood.value
        turn.score_0_10 = payload.new_score
        if payload.new_authenticity:
            turn.authenticity_likelihood = payload.new_authenticity

        # Recalculate session total score as average of turns
        all_turns_stmt = select(Turn).where(Turn.session_id == session_id)
        turns = (await db.execute(all_turns_stmt)).scalars().all()
        scored_turns = [t.score_0_10 for t in turns if t.score_0_10 is not None and t.question_type != "warmup"]
        if scored_turns:
            session.total_score = round(sum(scored_turns) / len(scored_turns), 2)
    else:
        session.total_score = payload.new_score
        if payload.new_authenticity:
            session.overall_authenticity_likelihood = payload.new_authenticity

    override_record = ScoreOverride(
        session_id=session.id,
        turn_id=payload.turn_id,
        teacher_id=teacher.id,
        original_score=original_score,
        new_score=payload.new_score,
        original_authenticity=original_flag,
        new_authenticity=payload.new_authenticity.value if payload.new_authenticity else None,
        reason=payload.reason,
    )
    db.add(override_record)

    # Log audit entry
    audit = AuditLog(
        user_id=teacher.id,
        action="SCORE_OVERRIDE",
        entity_type="score_override",
        entity_id=session.id,
        previous_state={"score": original_score, "authenticity": original_flag},
        new_state={"score": payload.new_score, "authenticity": payload.new_authenticity},
        reason=payload.reason,
    )
    db.add(audit)
    await db.flush()

    return {
        "message": "Override applied and recorded in audit log",
        "updated_session_score": session.total_score,
        "updated_session_flag": session.overall_authenticity_likelihood,
    }


@router.get("/sessions/{session_id}/export/csv")
async def export_session_csv(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Response:
    """Export session questions, scores, transcripts, and authenticity flags as CSV."""
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
    await ensure_session_access(db, teacher, session)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Turn #",
            "Topic",
            "Question",
            "Student Transcript",
            "Score (0-10)",
            "Authenticity Likelihood (Advisory)",
            "Authenticity Confidence (Advisory)",
            "Authenticity Reasons (Advisory)",
            "Feedback",
        ]
    )

    for turn in session.turns:
        reasons_str = "; ".join(turn.authenticity_reasons or [])
        writer.writerow(
            [
                turn.turn_number,
                turn.topic,
                turn.question_text,
                turn.transcript or "",
                turn.score_0_10 or "",
                turn.authenticity_likelihood.value,
                f"{turn.authenticity_confidence:.2f}" if turn.authenticity_confidence is not None else "",
                reasons_str,
                turn.feedback or "",
            ]
        )

    # Exports travel without the UI, so the advisory status must travel with them.
    writer.writerow([])
    writer.writerow([ADVISORY_EXPORT_NOTE])
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=viva_report_{session_id}.csv"},
    )


@router.get("/sessions/{session_id}/export/pdf")
async def export_session_pdf(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    teacher: Annotated[User, Depends(require_role([UserRole.TEACHER, UserRole.ADMIN]))],
) -> Response:
    """Export the session report (questions, answers, scores, advisory authenticity) as PDF."""
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
    await ensure_session_access(db, teacher, session)

    pdf_bytes = await asyncio.to_thread(build_session_pdf, session, list(session.turns))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=viva_report_{session_id}.pdf"},
    )
