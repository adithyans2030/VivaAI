"""Audio retention policy: sessions older than the window lose their audio, whatever their status."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.session import SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.turn import Turn
from app.models.user import User
from app.services import retention
from tests.conftest import test_async_session


def _audio_dir(root: Path, session_id: str) -> Path:
    d = root / session_id
    d.mkdir(parents=True)
    (d / "turn_1.wav").write_bytes(b"RIFF")
    return d


async def test_cleanup_purges_all_expired_sessions_including_abandoned(
    student_user: User, teacher_user: User, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "AUDIO_STORAGE_PATH", tmp_path)
    old = datetime.now(timezone.utc) - timedelta(days=45)

    async with test_async_session() as db:
        db.add(Subject(id="subj-ret", name="OS", code="RET1", description="", teacher_id=teacher_user.id))
        cases = {
            "old-done": (SessionStatus.COMPLETED, old),
            "old-active": (SessionStatus.IN_PROGRESS, old),
            "new-done": (SessionStatus.COMPLETED, datetime.now(timezone.utc)),
        }
        for sid, (status, created) in cases.items():
            db.add(
                VivaSession(
                    id=sid,
                    student_id=student_user.id,
                    subject_id="subj-ret",
                    status=status,
                    recording_consent=True,
                    created_at=created,
                )
            )
            db.add(Turn(session_id=sid, turn_number=1, question_text="Q", student_audio_path=f"{sid}/turn_1.wav"))
            _audio_dir(tmp_path, sid)
        await db.commit()

        assert await retention.cleanup_expired_audio(db, retention_days=30) == 2

        turns = {t.session_id: t for t in (await db.execute(select(Turn))).scalars()}

    assert not (tmp_path / "old-done").exists()
    assert turns["old-done"].student_audio_path is None
    # An in-progress session past the window was abandoned: its audio goes too.
    assert not (tmp_path / "old-active").exists() and turns["old-active"].student_audio_path is None
    # Recent sessions keep their audio.
    assert (tmp_path / "new-done").exists() and turns["new-done"].student_audio_path


async def test_cleanup_clears_stale_paths_when_directory_already_gone(
    student_user: User, teacher_user: User, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "AUDIO_STORAGE_PATH", tmp_path)
    async with test_async_session() as db:
        db.add(Subject(id="subj-ret2", name="OS", code="RET2", description="", teacher_id=teacher_user.id))
        db.add(
            VivaSession(
                id="gone",
                student_id=student_user.id,
                subject_id="subj-ret2",
                status=SessionStatus.CANCELLED,
                recording_consent=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=90),
            )
        )
        db.add(Turn(session_id="gone", turn_number=1, question_text="Q", student_audio_path="gone/turn_1.wav"))
        await db.commit()

        assert await retention.cleanup_expired_audio(db, retention_days=30) == 0

    async with test_async_session() as db:
        turn = (await db.execute(select(Turn).where(Turn.session_id == "gone"))).scalar_one()
    assert turn.student_audio_path is None


async def test_retention_loop_survives_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def flaky(db: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("disk unavailable")
        return 0

    monkeypatch.setattr(retention, "cleanup_expired_audio", flaky)
    task = asyncio.create_task(retention.run_retention_forever(test_async_session, interval_seconds=0))
    while calls < 3:
        await asyncio.sleep(0)
    task.cancel()
    assert calls >= 3
