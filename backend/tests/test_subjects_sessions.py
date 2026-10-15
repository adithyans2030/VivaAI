"""Unit and integration tests for subjects, sessions, consent, and teacher overrides."""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.asyncio
async def test_subject_and_session_lifecycle(
    client: AsyncClient,
    teacher_user: User,
    student_user: User,
):
    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)
    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)

    # 1. Teacher creates a subject
    subject_resp = await client.post(
        "/api/v1/subjects",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "name": "Operating Systems",
            "code": "CS301",
            "description": "Processes, Threads, CPU Scheduling and Deadlocks",
        },
    )
    assert subject_resp.status_code == 201
    subject_data = subject_resp.json()
    subject_id = subject_data["id"]
    assert subject_data["code"] == "CS301"

    # 2. Student lists subjects
    list_resp = await client.get(
        "/api/v1/subjects",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert list_resp.status_code == 200
    subjects = list_resp.json()
    assert len(subjects) >= 1
    assert any(s["code"] == "CS301" for s in subjects)

    # 3. Student creates a viva session
    session_resp = await client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"subject_id": subject_id},
    )
    assert session_resp.status_code == 201
    session_data = session_resp.json()
    session_id = session_data["id"]
    assert session_data["recording_consent"] is False

    # 4. Student gives recording consent
    consent_resp = await client.post(
        f"/api/v1/sessions/{session_id}/consent",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"recording_consent": True},
    )
    assert consent_resp.status_code == 200
    assert consent_resp.json()["recording_consent"] is True

    # 5. Teacher inspects session details
    detail_resp = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["subject_code"] == "CS301"
    assert detail["student_name"] == "Ada Lovelace"

    # 6. Teacher adds notes
    notes_resp = await client.post(
        f"/api/v1/reports/sessions/{session_id}/notes",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"teacher_notes": "Student demonstrated good conceptual clarity on deadlock conditions."},
    )
    assert notes_resp.status_code == 200

    # 7. Teacher overrides score with reason
    override_resp = await client.post(
        f"/api/v1/reports/sessions/{session_id}/override",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "new_score": 8.5,
            "new_authenticity": "low",
            "reason": "Clear explanation with personal analogies and intuitive diagrams.",
        },
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["updated_session_score"] == 8.5

    # 8. Export CSV
    export_resp = await client.get(
        f"/api/v1/reports/sessions/{session_id}/export/csv",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert export_resp.status_code == 200
    assert "Turn #" in export_resp.text
