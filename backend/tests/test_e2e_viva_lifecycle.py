"""End-to-end viva lifecycle across all three roles.

admin provisions teacher -> teacher creates subject -> student self-registers ->
session + consent -> single-use WS ticket -> question / answer / feedback ->
end session -> teacher report, override (audited) and CSV export.

LLM and STT are the mock providers enforced by conftest, so this runs without a GPU.
"""

import base64
from typing import AsyncGenerator, Iterator

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

import app.ws.session_handler as ws_handler
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.audit import AuditLog
from app.models.user import User
from tests.conftest import test_async_session


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Sync client (needed for WebSockets) bound to the in-memory test database."""
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_full_viva_lifecycle(client: TestClient, admin_user: User) -> None:
    admin_token = create_access_token(subject=admin_user.id, role=admin_user.role.value)

    # 1. Admin provisions a teacher (public registration cannot create teachers)
    resp = client.post(
        "/api/v1/auth/admin/users",
        headers=_auth(admin_token),
        json={"email": "e2e.teacher@vivaiq.edu", "full_name": "E2E Teacher", "password": "TeacherPass1!"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "teacher"
    teacher_token = _login(client, "e2e.teacher@vivaiq.edu", "TeacherPass1!")["access_token"]

    # 2. Teacher creates a subject
    resp = client.post(
        "/api/v1/subjects",
        headers=_auth(teacher_token),
        json={"name": "Operating Systems", "code": "CS301", "description": "Deadlocks and scheduling"},
    )
    assert resp.status_code == 201, resp.text
    subject_id = resp.json()["id"]

    # 3. Student self-registers; a requested admin role is ignored
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "e2e.student@vivaiq.edu",
            "password": "StudentPass1!",
            "full_name": "E2E Student",
            "role": "admin",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "student"
    student_token = _login(client, "e2e.student@vivaiq.edu", "StudentPass1!")["access_token"]

    # 4. Session is created without consent; tickets work, but the socket refuses until consent
    resp = client.post("/api/v1/sessions", headers=_auth(student_token), json={"subject_id": subject_id})
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    assert resp.json()["recording_consent"] is False

    resp = client.post(
        f"/api/v1/sessions/{session_id}/consent", headers=_auth(student_token), json={"recording_consent": True}
    )
    assert resp.status_code == 200
    assert resp.json()["recording_consent"] is True

    # 5. Single-use ticket authenticates the WebSocket
    resp = client.post(f"/api/v1/sessions/{session_id}/ws-ticket", headers=_auth(student_token))
    assert resp.status_code == 200
    ticket = resp.json()["ticket"]

    with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "session_state"

        # Warm-up first (baseline only, never scored), then a real question.
        scores = []
        for expected_type_is_warmup in (True, False):
            ws.send_json({"type": "request_question", "payload": {}})
            assert ws.receive_json()["payload"]["state"] == "examiner_speaking"
            question = ws.receive_json()
            assert question["type"] == "question"
            assert question["payload"]["question_text"]
            assert (question["payload"]["question_type"] == "warmup") is expected_type_is_warmup
            turn_id = question["payload"]["turn_id"]
            assert ws.receive_json()["payload"]["state"] == "listening"

            chunk = base64.b64encode(bytes(800)).decode("utf-8")
            ws.send_json({"type": "audio_chunk", "payload": {"turn_id": turn_id, "chunk_index": 0, "audio_b64": chunk}})
            ws.send_json({"type": "speech_end", "payload": {"turn_id": turn_id, "duration_ms": 1200}})

            assert ws.receive_json()["payload"]["state"] == "processing"
            transcript = ws.receive_json()
            assert transcript["type"] == "transcript"
            assert transcript["payload"]["text"]
            feedback = ws.receive_json()
            assert feedback["type"] == "feedback"
            assert 0 <= feedback["payload"]["score_0_10"] <= 10
            assert feedback["payload"]["counts_toward_score"] is not expected_type_is_warmup
            scores.append(feedback["payload"]["score_0_10"])

        ws.send_json({"type": "end_session", "payload": {}})
        complete = ws.receive_json()
        assert complete["type"] == "session_complete"
        assert complete["payload"]["total_score"] == scores[1]  # warm-up excluded

    # The ticket was consumed: reusing it must fail
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?ticket={ticket}") as ws:
            ws.receive_json()

    # 6. Teacher reviews the report: it carries the transcript and advisory authenticity reasons
    resp = client.get(f"/api/v1/reports/sessions/{session_id}", headers=_auth(teacher_token))
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["student_name"] == "E2E Student"
    assert len(report["turns"]) == 2
    assert all(t["transcript"] for t in report["turns"])
    assert isinstance(report["authenticity_reasons"], list)

    # Students cannot use teacher-only tooling
    resp = client.get(f"/api/v1/reports/sessions/{session_id}/export/csv", headers=_auth(student_token))
    assert resp.status_code == 403

    # 7. Teacher override is applied and audited
    resp = client.post(
        f"/api/v1/reports/sessions/{session_id}/override",
        headers=_auth(teacher_token),
        json={
            "turn_id": turn_id,
            "new_score": 9.0,
            "new_authenticity": "low",
            "reason": "Verified in follow-up discussion",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated_session_score"] == 9.0

    async with test_async_session() as db:
        audits = (await db.execute(select(AuditLog).where(AuditLog.entity_id == session_id))).scalars().all()
    assert [a.action for a in audits] == ["SCORE_OVERRIDE"]

    # 8. CSV export reflects the override
    resp = client.get(f"/api/v1/reports/sessions/{session_id}/export/csv", headers=_auth(teacher_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "9.0" in resp.text
    assert "Authenticity Likelihood (Advisory)" in resp.text
    assert "ADVISORY ONLY" in resp.text

    # 9. Completed sessions cannot be reconnected to
    resp = client.post(f"/api/v1/sessions/{session_id}/ws-ticket", headers=_auth(student_token))
    assert resp.status_code == 400


async def test_refresh_token_rotation_revokes_old_token(client: TestClient, student_user: User) -> None:
    tokens = _login(client, "student@vivaiq.edu", "student123")

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    assert first.json()["refresh_token"] != tokens["refresh_token"]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


async def test_upload_rejects_mismatched_magic_bytes(client: TestClient, teacher_user: User) -> None:
    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)
    subject = client.post(
        "/api/v1/subjects",
        headers=_auth(teacher_token),
        json={"name": "Networks", "code": "CS302", "description": "OSI model"},
    ).json()

    resp = client.post(
        f"/api/v1/subjects/{subject['id']}/documents",
        headers=_auth(teacher_token),
        files={"file": ("notes.pdf", b"MZ\x90\x00not-really-a-pdf", "application/pdf")},
    )
    assert resp.status_code in (400, 415)


async def test_student_can_export_own_data(client: TestClient, student_user: User) -> None:
    token = create_access_token(subject=student_user.id, role=student_user.role.value)
    resp = client.get("/api/v1/auth/me/export-data", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["user_profile"]["email"] == "student@vivaiq.edu"
