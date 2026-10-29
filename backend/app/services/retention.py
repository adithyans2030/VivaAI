"""Audio and data retention policy management (WS-2.5)."""

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.session import SessionStatus, VivaSession


async def cleanup_expired_audio(db: AsyncSession, retention_days: Optional[int] = None) -> int:
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
    paths_cleared = False
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
                paths_cleared = True

    if deleted_count > 0 or paths_cleared:
        await db.commit()
    if deleted_count > 0:
        logger.info(
            f"Retention policy executed: purged audio for {deleted_count} expired viva sessions (older than {days} days)"
        )

    return deleted_count


async def run_retention_forever(
    session_factory: async_sessionmaker[AsyncSession], interval_seconds: float = 24 * 3600
) -> None:
    """Apply the retention policy at startup and then on a fixed interval until cancelled."""
    while True:
        try:
            async with session_factory() as db:
                await cleanup_expired_audio(db)
        except Exception as e:  # never let a bad run stop future runs
            logger.error(f"Retention sweep failed: {e}")
        await asyncio.sleep(interval_seconds)
