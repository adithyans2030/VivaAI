"""Tests for WS-4 WebSocket session handler fixes: buffer capping, invalid turn rejection, empty audio defense, repeat limit, and recovery state."""

from typing import AsyncGenerator, cast

import pytest
from fastapi import WebSocket
from starlette.testclient import TestClient

import app.ws.session_handler as ws_handler
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.ws.connection_manager import manager
from tests.conftest import test_async_session


def test_buffer_overflow_defense():
    """Verify that audio buffer exceeds cap is rejected without memory exhaustion."""
    sess_id = "test-overflow-session"
    manager.consume_audio_buffer(sess_id)

    # 1MB chunk
    one_mb = b"\x00" * (1024 * 1024)
    # Append 9 MB (within 9.6MB limit)
    for _ in range(9):
        manager.append_audio_chunk(sess_id, one_mb)

    # Appending another 1MB exceeds 9.6MB
    with pytest.raises(BufferError) as exc_info:
        manager.append_audio_chunk(sess_id, one_mb)
    assert "AUDIO_BUFFER_OVERFLOW" in str(exc_info.value)
    manager.consume_audio_buffer(sess_id)


def test_clear_audio_buffer_discards_abandoned_recording():
    """A repeat/new question must not prepend the abandoned WebM stream to the next answer."""
    sess_id = "test-clear-session"
    manager.append_audio_chunk(sess_id, b"old-recording")
    manager.clear_audio_buffer(sess_id)
    manager.append_audio_chunk(sess_id, b"new-answer")
    assert manager.consume_audio_buffer(sess_id) == b"new-answer"


@pytest.mark.asyncio
async def test_stale_disconnect_keeps_replacement_connection():
    """On reconnect the old handler exits last; it must not unregister the new socket."""

    class FakeWS:
        async def accept(self):
            pass

        async def close(self, code=1000, reason=""):
            pass

        async def send_json(self, message):
            self.sent = message

    sess_id = "test-reconnect-session"
    fake_new = FakeWS()
    old_ws, new_ws = cast(WebSocket, FakeWS()), cast(WebSocket, fake_new)
    await manager.connect(sess_id, old_ws)
    await manager.connect(sess_id, new_ws)

    await manager.disconnect(sess_id, old_ws)
    assert await manager.send_json(sess_id, {"type": "pong"}) is True
    assert fake_new.sent == {"type": "pong"}

    await manager.disconnect(sess_id, new_ws)
    assert await manager.send_json(sess_id, {"type": "pong"}) is False


def test_ws4_handler_edge_cases(
    student_user: User,
    teacher_user: User,
    monkeypatch,
):
    """Verify empty audio, invalid base64, and reconnect recovery state handling."""
    monkeypatch.setattr(ws_handler, "async_session_factory", test_async_session)

    async def override_get_db() -> AsyncGenerator:
        async with test_async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)
    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)

    with TestClient(app) as client:
        # Create subject and session
        subj_resp = client.post(
            "/api/v1/subjects",
            headers={"Authorization": f"Bearer {teacher_token}"},
            json={"name": "Distributed Systems", "code": "CS401", "description": "Consensus and Raft"},
        )
        subject_id = subj_resp.json()["id"]

        sess_resp = client.post(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"subject_id": subject_id},
        )
        session_id = sess_resp.json()["id"]

        client.post(
            f"/api/v1/sessions/{session_id}/consent",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"recording_consent": True},
        )

        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?token={student_token}") as ws:
            # 1. Verify reconnect session_state sent on connect
            state_event = ws.receive_json()
            assert state_event["type"] == "session_state"
            assert state_event["payload"]["session_id"] == session_id

            # 2. Test invalid base64 chunk
            ws.send_json({"type": "audio_chunk", "payload": {"audio_b64": "!!!NOT_VALID_BASE64!!!"}})
            b64_err = ws.receive_json()
            assert b64_err["type"] == "error"
            assert b64_err["payload"]["code"] == "INVALID_AUDIO_ENCODING"

            # 3. Request question
            ws.send_json({"type": "request_question", "payload": {}})
            ws.receive_json()  # state_change examiner_speaking
            q_msg = ws.receive_json()  # question
            assert q_msg["type"] == "question"
            turn_id = q_msg["payload"]["turn_id"]
            ws.receive_json()  # state_change listening

            # 4. Test empty audio on speech_end -> EMPTY_AUDIO error and reset to listening
            ws.send_json({"type": "speech_end", "payload": {"turn_id": turn_id}})
            empty_err = ws.receive_json()
            assert empty_err["type"] == "error"
            assert empty_err["payload"]["code"] == "EMPTY_AUDIO"

            listen_state = ws.receive_json()
            assert listen_state["type"] == "state_change"
            assert listen_state["payload"]["state"] == "listening"

    app.dependency_overrides.clear()
