"""Tests for real-time viva session WebSocket."""

import base64
from typing import AsyncGenerator

from starlette.testclient import TestClient

import app.ws.session_handler as ws_handler
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from tests.conftest import test_async_session


def test_websocket_viva_flow(
    student_user: User,
    teacher_user: User,
    monkeypatch,
):
    # Route async_session_factory to test in-memory database
    monkeypatch.setattr(ws_handler, "async_session_factory", test_async_session)

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
            # 6.1 Reconnection handling: Server sends session_state immediately on connect
            init_msg = ws.receive_json()
            assert init_msg["type"] == "session_state"
            assert init_msg["payload"]["session_id"] == session_id

            # 6.2 Ping / Pong
            ws.send_json({"type": "ping", "payload": {"timestamp": 12345678}})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

            # 6.3 Request initial question
            ws.send_json({"type": "request_question", "payload": {}})
            # Examiner speaking state
            msg_state1 = ws.receive_json()
            assert msg_state1["type"] == "state_change"
            assert msg_state1["payload"]["state"] == "examiner_speaking"

            # Question event
            msg_q = ws.receive_json()
            assert msg_q["type"] == "question"
            assert msg_q["payload"]["turn_number"] == 1
            turn_id = msg_q["payload"]["turn_id"]

            # Listening state
            msg_listen = ws.receive_json()
            assert msg_listen["type"] == "state_change"
            assert msg_listen["payload"]["state"] == "listening"

            # 6.4 Test repeat question logic and 1-repeat limit
            ws.send_json({"type": "repeat_question", "payload": {"turn_id": turn_id}})
            rep_state = ws.receive_json()
            assert rep_state["type"] == "state_change"
            rep_q = ws.receive_json()
            assert rep_q["type"] == "question"
            assert rep_q["payload"]["is_repeat"] is True
            rep_listen = ws.receive_json()
            assert rep_listen["type"] == "state_change"

            # Second repeat must be rejected with REPEAT_LIMIT_EXCEEDED
            ws.send_json({"type": "repeat_question", "payload": {"turn_id": turn_id}})
            rep_err = ws.receive_json()
            assert rep_err["type"] == "error"
            assert rep_err["payload"]["code"] == "REPEAT_LIMIT_EXCEEDED"

            # 6.5 Reject speech_end on nonexistent turn_id
            ws.send_json({"type": "speech_end", "payload": {"turn_id": "nonexistent-turn-id"}})
            err_turn = ws.receive_json()
            assert err_turn["type"] == "error"
            assert err_turn["payload"]["code"] == "INVALID_TURN"

            # 6.6 Stream valid audio chunks
            dummy_pcm = b"\x00\x00" * 400
            chunk_b64 = base64.b64encode(dummy_pcm).decode("utf-8")
            ws.send_json(
                {
                    "type": "audio_chunk",
                    "payload": {"turn_id": turn_id, "chunk_index": 0, "audio_b64": chunk_b64},
                }
            )

            # Send speech_end with valid turn_id
            ws.send_json(
                {
                    "type": "speech_end",
                    "payload": {"turn_id": turn_id, "duration_ms": 1200},
                }
            )

            # Expect state_change to processing with real turn_number
            msg1 = ws.receive_json()
            assert msg1["type"] == "state_change"
            assert msg1["payload"]["state"] == "processing"
            assert msg1["payload"]["turn_number"] == 1

            # Expect transcript with word timestamps
            msg2 = ws.receive_json()
            assert msg2["type"] == "transcript"
            assert "text" in msg2["payload"]
            assert len(msg2["payload"]["words"]) > 0

            # Expect feedback evaluated by grader
            msg_feedback = ws.receive_json()
            assert msg_feedback["type"] == "feedback"
            assert "score_0_10" in msg_feedback["payload"]

            # 6.7 End session cleanly
            ws.send_json({"type": "end_session", "payload": {}})
            msg3 = ws.receive_json()
            assert msg3["type"] == "session_complete"
            # Only the warm-up was answered, and it never counts: the session is not graded.
            assert msg3["payload"]["total_score"] is None

    app.dependency_overrides.clear()
