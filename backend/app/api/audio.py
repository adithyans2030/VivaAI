"""Audio streaming endpoint for student turn recordings with strict access control (WS-2.5)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_session_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.session import VivaSession
from app.models.turn import Turn
from app.models.user import User

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/{session_id}/{turn_id}")
async def get_turn_audio(
    session_id: str,
    turn_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream or download a candidate's recorded audio for a viva turn."""
    # Verify session existence
    stmt = select(VivaSession).where(VivaSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    await ensure_session_access(db, current_user, session)

    # Check file on disk
    audio_path = settings.AUDIO_STORAGE_PATH / session_id / f"{turn_id}.wav"
    if not audio_path.exists():
        # Also check relative path from Turn record if available
        turn_stmt = select(Turn).where(Turn.id == turn_id, Turn.session_id == session_id)
        turn = (await db.execute(turn_stmt)).scalar_one_or_none()
        if turn and turn.student_audio_path:
            p = Path(turn.student_audio_path)
            if p.exists():
                audio_path = p

    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio recording for turn '{turn_id}' not found on storage",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"turn_{turn_id}.wav",
    )
