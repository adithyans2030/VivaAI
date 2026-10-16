"""Audio and data retention policy management (WS-2.5)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.session import SessionStatus, VivaSession
from app.models.turn import Turn


async def cleanup_expired_audio(
    db: AsyncSession, retention_days: Optional[int] = None
) -> int:
    """Scan and delete audio files for completed sessions exceeding the retention window."""
    days = retention_days if retention_days is not None else settings.AUDIO_RETENTION_DAYS
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(VivaSession)
        .where(
            VivaSession.created_at < cutoff_date,
            VivaSession.status.in_([SessionStatus.COMPLETED, SessionStatus.CANCELLED]),
        )
        .options(selectinload(VivaSession.turns))
    )
    result = await db.execute(stmt)
    expired_sessions = result.scalars().all()

    deleted_count = 0
    for session in expired_sessions:
        # Check and remove physical audio directory
        session_audio_dir = settings.AUDIO_STORAGE_PATH / session.id
        if session_audio_dir.exists() and session_audio_dir.is_dir():
            try:
                shutil.rmtree(session_audio_dir)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete expired audio directory for session {session.id}: {e}")

        # Clear audio file paths in turns
        for turn in session.turns:
            if turn.student_audio_path:
                turn.student_audio_path = None

    if deleted_count > 0:
        await db.commit()
        logger.info(f"Retention policy executed: purged audio for {deleted_count} expired viva sessions (older than {days} days)")

    return deleted_count
