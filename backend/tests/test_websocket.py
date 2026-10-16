"""Tests for real-time viva session WebSocket."""

import base64
from typing import AsyncGenerator
import pytest
from starlette.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.services.grader import GraderService
from app.services.llm.mock import MockLLMProvider
import app.ws.session_handler as ws_handler
from tests.conftest import test_async_session


def test_websocket_viva_flow(
    student_user: User,
    teacher_user: User,
    monkeypatch,
):
    # Route async_session_factory to test in-memory database
    monkeypatch.setattr(ws_handler, "async_session_factory", test_async_session)
    monkeypatch.setattr(
        ws_handler,
        "get_grader_service",
        lambda: GraderService(llm_provider=MockLLMProvider()),
    )

    # Route get_db dependency to test in-memory database
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
        # 1. Test unauthorized connection (invalid token)
        try:
            with client.websocket_connect("/api/v1/ws/sessions/invalid-session?token=bad-token") as ws:
                pass
        except Exception:
            pass

        # 2. Setup subject via HTTP API
        subj_resp = client.post(
            "/api/v1/subjects",
            headers={"Authorization": f"Bearer {teacher_token}"},
            json={"name": "Computer Networks", "code": "CS302", "description": "OSI and TCP/IP"},
        )
        assert subj_resp.status_code == 201
        subject_id = subj_resp.json()["id"]

        # 3. Create viva session
        sess_resp = client.post(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"subject_id": subject_id},
        )
        assert sess_resp.status_code == 201
        session_id = sess_resp.json()["id"]

        # 4. Connect before consent -> Expect rejection
        rejected = False
        try:
            with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?token={student_token}") as ws:
                pass
        except Exception:
            rejected = True
        assert rejected is True

        # 5. Record consent
        consent_resp = client.post(
            f"/api/v1/sessions/{session_id}/consent",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"recording_consent": True},
        )
        assert consent_resp.status_code == 200

        # 6. Connect WebSocket successfully after consent
        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?token={student_token}") as ws:
            # Ping / Pong
            ws.send_json({"type": "ping", "payload": {"timestamp": 12345678}})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

            # Stream audio chunk
            dummy_pcm = b"\x00\x00" * 400
            chunk_b64 = base64.b64encode(dummy_pcm).decode("utf-8")
            ws.send_json({
                "type": "audio_chunk",
                "payload": {"turn_id": "turn-test-1", "chunk_index": 0, "audio_b64": chunk_b64},
            })

            # Send speech_end
            ws.send_json({
                "type": "speech_end",
                "payload": {"turn_id": "turn-test-1", "duration_ms": 1200},
            })

            # Expect state_change to processing
            msg1 = ws.receive_json()
            assert msg1["type"] == "state_change"
            assert msg1["payload"]["state"] == "processing"

            # Expect transcript with word timestamps
            msg2 = ws.receive_json()
            assert msg2["type"] == "transcript"
            assert "text" in msg2["payload"]
            assert len(msg2["payload"]["words"]) > 0

            # Expect feedback evaluated by grader
            msg_feedback = ws.receive_json()
            assert msg_feedback["type"] == "feedback"
            assert "score_0_10" in msg_feedback["payload"]

            # End session
            ws.send_json({"type": "end_session", "payload": {}})
            msg3 = ws.receive_json()
            assert msg3["type"] == "session_complete"
            assert msg3["payload"]["total_score"] > 0

    app.dependency_overrides.clear()
