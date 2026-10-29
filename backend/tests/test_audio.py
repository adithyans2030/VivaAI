"""Tests for audio streaming API endpoint."""

import wave

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.session import SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.turn import Turn
from app.models.user import User
from tests.conftest import test_async_session


@pytest.mark.asyncio
async def test_audio_streaming_endpoint(student_user: User, teacher_user: User):
    """Verify audio retrieval and student vs teacher authorization."""

    async def override_get_db():
        async with test_async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)
    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)

    # 1. Setup session, turn, and actual audio WAV file
    session_id = "sess-audio-test"
    turn_id = "turn-audio-test"

    session_dir = settings.AUDIO_STORAGE_PATH / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    audio_path = session_dir / f"{turn_id}.wav"

    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(bytes(32000))

    async with test_async_session() as db:
        subj = Subject(
            id="cs301-audio",
            name="Audio Test Subject",
            code="CS301-A",
            teacher_id=teacher_user.id,
        )
        sess = VivaSession(
            id=session_id,
            student_id=student_user.id,
            subject_id=subj.id,
            status=SessionStatus.COMPLETED,
            recording_consent=True,
        )
        turn = Turn(
            id=turn_id,
            session_id=session_id,
            turn_number=1,
            question_text="Audio test question",
            student_audio_path=str(audio_path),
        )
        db.add(subj)
        db.add(sess)
        db.add(turn)
        await db.commit()

    try:
        with TestClient(app) as client:
            # 2. Teacher fetches audio -> 200 OK
            res_teacher = client.get(
                f"/api/v1/audio/{session_id}/{turn_id}",
                headers={"Authorization": f"Bearer {teacher_token}"},
            )
            assert res_teacher.status_code == 200
            assert res_teacher.headers["content-type"] == "audio/wav"
            assert len(res_teacher.content) > 0

            # 3. Student owner fetches audio -> 200 OK
            res_student = client.get(
                f"/api/v1/audio/{session_id}/{turn_id}",
                headers={"Authorization": f"Bearer {student_token}"},
            )
            assert res_student.status_code == 200

            # 4. Non-existent audio -> 404
            res_404 = client.get(
                f"/api/v1/audio/{session_id}/nonexistent-turn",
                headers={"Authorization": f"Bearer {teacher_token}"},
            )
            assert res_404.status_code == 404

            # 5. Test session turn audio route alias (WS-7)
            res_alias = client.get(
                f"/api/v1/sessions/{session_id}/turns/{turn_id}/audio",
                headers={"Authorization": f"Bearer {teacher_token}"},
            )
            assert res_alias.status_code == 200
            assert res_alias.headers["content-type"] == "audio/wav"
            assert len(res_alias.content) > 0
    finally:
        app.dependency_overrides.clear()
        if audio_path.exists():
            audio_path.unlink()
        if session_dir.exists():
            try:
                session_dir.rmdir()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_tts_providers():
    """Verify MockTTS, BrowserTTS, and EdgeTTS providers."""
    from app.services.tts import BrowserTTSProvider, EdgeTTSProvider, MockTTSProvider

    # 1. Browser TTS returns None (client uses browser speech synthesis)
    browser_tts = BrowserTTSProvider()
    assert await browser_tts.synthesize_audio("Hello") is None

    # 2. Mock TTS returns valid sine wave WAV
    mock_tts = MockTTSProvider()
    wav_bytes = await mock_tts.synthesize_audio("Test question")
    assert wav_bytes is not None
    assert wav_bytes[:4] == b"RIFF"

    # 3. EdgeTTS instance initializes properly
    edge_tts_inst = EdgeTTSProvider(voice="en-US-JennyNeural")
    assert edge_tts_inst.voice == "en-US-JennyNeural"
