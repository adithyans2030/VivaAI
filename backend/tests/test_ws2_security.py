"""Tests for WS-2 Security Hardening:
- Role escalation prevention (WS-2.1)
- Password length requirements (WS-2.2)
- Single-use WebSocket tickets and refresh token rotation (WS-2.3)
- Upload path sanitization and magic byte validation (WS-2.4)
- Audio privacy, access control, and GDPR data export/deletion (WS-2.5)
"""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.session import SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.auth_state import consume_ticket
from tests.conftest import test_async_session


@pytest.mark.asyncio
async def test_registration_forces_student_role(client: AsyncClient, db_session: AsyncSession):
    """WS-2.1: Public self-registration must force STUDENT role, even if client attempts role escalation."""
    reg_payload = {
        "email": "hacker@test.edu",
        "full_name": "Privilege Escalation Attempt",
        "password": "securepassword123",
        "role": "admin",  # Attacker attempts to become admin
    }
    resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "student", "Role must be forced to student on public registration"

    # Verify directly in database
    user = (await db_session.execute(select(User).where(User.email == "hacker@test.edu"))).scalar_one_or_none()
    assert user is not None
    assert user.role == UserRole.STUDENT


@pytest.mark.asyncio
async def test_admin_user_creation_access_control(
    client: AsyncClient,
    student_user: User,
    admin_user: User,
):
    """WS-2.1: Only authenticated administrators can provision teacher/admin accounts."""
    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)
    admin_token = create_access_token(subject=admin_user.id, role=admin_user.role.value)

    payload = {
        "email": "newteacher@school.edu",
        "full_name": "Prof. Margaret Hamilton",
        "password": "teachersecurepassword123",
        "role": "teacher",
    }

    # Non-admin attempt should be forbidden (403)
    resp_student = await client.post(
        "/api/v1/auth/admin/users",
        headers={"Authorization": f"Bearer {student_token}"},
        json=payload,
    )
    assert resp_student.status_code == 403

    # Admin attempt should succeed (201)
    resp_admin = await client.post(
        "/api/v1/auth/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert resp_admin.status_code == 201
    assert resp_admin.json()["role"] == "teacher"


@pytest.mark.asyncio
async def test_password_minimum_length_enforced(client: AsyncClient):
    """WS-2.2: Passwords under 8 characters must be rejected with 422."""
    short_pw_payload = {
        "email": "shortpw@school.edu",
        "full_name": "Short Password",
        "password": "short7!",  # 7 characters
    }
    resp = await client.post("/api/v1/auth/register", json=short_pw_payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ws_ticket_single_use_and_isolation(
    client: AsyncClient,
    student_user: User,
    teacher_user: User,
    db_session: AsyncSession,
):
    """WS-2.3: WebSocket tickets must be short-lived, single-use, and scoped to session owner."""
    # Create other student user
    other_student = User(
        email="other@vivaiq.edu",
        hashed_password="hashed_password_123",
        full_name="Other Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(other_student)

    # Create subject and session
    subj = Subject(name="Networks", code="NET101", teacher_id=teacher_user.id)
    db_session.add(subj)
    await db_session.flush()

    sess = VivaSession(student_id=student_user.id, subject_id=subj.id, status=SessionStatus.CREATED)
    db_session.add(sess)
    await db_session.commit()

    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)
    other_student_token = create_access_token(subject=other_student.id, role=other_student.role.value)

    # Unauthorized student cannot get ticket for this session
    unauth_resp = await client.post(
        f"/api/v1/sessions/{sess.id}/ws-ticket",
        headers={"Authorization": f"Bearer {other_student_token}"},
    )
    assert unauth_resp.status_code == 403

    # Authorized student receives ticket
    ticket_resp = await client.post(
        f"/api/v1/sessions/{sess.id}/ws-ticket",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert ticket_resp.status_code == 200
    ticket = ticket_resp.json()["ticket"]
    assert ticket.startswith("wst_")
    assert ticket_resp.json()["expires_in"] == 30

    # First ticket consumption succeeds
    async with test_async_session() as db:
        grant = await consume_ticket(db, ticket, sess.id)
    assert grant.user_id == student_user.id

    # Second consumption fails (single-use guarantee), even from a fresh DB session
    async with test_async_session() as db:
        with pytest.raises(ValueError, match="already been used"):
            await consume_ticket(db, ticket, sess.id)

    # A ticket is bound to its session
    async with test_async_session() as db:
        with pytest.raises(ValueError, match="does not match"):
            await consume_ticket(db, ticket, "another-session")


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation(client: AsyncClient):
    """WS-2.3: Refresh tokens must rotate on each refresh, and old tokens cannot be reused."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@test.edu", "full_name": "Rotation Test", "password": "securepassword123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rotate@test.edu", "password": "securepassword123"},
    )
    assert login_resp.status_code == 200
    initial_refresh = login_resp.json()["refresh_token"]

    # First refresh succeeds
    ref_resp1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert ref_resp1.status_code == 200
    new_refresh = ref_resp1.json()["refresh_token"]
    assert new_refresh != initial_refresh

    # Attempt to reuse initial refresh token must fail (401)
    ref_resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert ref_resp2.status_code == 401


@pytest.mark.asyncio
async def test_upload_magic_bytes_and_path_sanitization(
    client: AsyncClient,
    teacher_user: User,
    db_session: AsyncSession,
):
    """WS-2.4: Uploads must sanitize malicious filenames and reject files with mismatched magic bytes."""
    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)

    subj = Subject(name="Security", code="SEC101", teacher_id=teacher_user.id)
    db_session.add(subj)
    await db_session.commit()

    # 1. Mismatched magic bytes: claims to be PDF but contains random text
    fake_pdf = b"This is not a real PDF document!"
    resp_fake = await client.post(
        f"/api/v1/subjects/{subj.id}/documents",
        headers={"Authorization": f"Bearer {teacher_token}"},
        files={"file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert resp_fake.status_code == 400
    assert "File content does not match expected format" in resp_fake.json()["detail"]

    # 2. Valid PDF magic bytes with path traversal attempt in filename
    valid_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    malicious_filename = "../../../etc/passwd.pdf"
    resp_valid = await client.post(
        f"/api/v1/subjects/{subj.id}/documents",
        headers={"Authorization": f"Bearer {teacher_token}"},
        files={"file": (malicious_filename, io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert resp_valid.status_code == 201
    saved_doc = resp_valid.json()
    assert ".." not in saved_doc["filename"], "Filename must be sanitized against path traversal"
    assert "/" not in saved_doc["filename"]
    assert "\\" not in saved_doc["filename"]


@pytest.mark.asyncio
async def test_audio_access_control(
    client: AsyncClient,
    student_user: User,
    teacher_user: User,
    db_session: AsyncSession,
):
    """WS-2.5: Only the session's student or the assigned subject teacher can fetch audio."""
    # Create other student and unassigned teacher users
    other_student = User(
        email="unauth_student@vivaiq.edu",
        hashed_password="hashed_password_123",
        full_name="Unauthorized Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    unassigned_teacher = User(
        email="unassigned_teacher@vivaiq.edu",
        hashed_password="hashed_password_123",
        full_name="Unassigned Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_student)
    db_session.add(unassigned_teacher)

    subj = Subject(name="Databases", code="DB201", teacher_id=teacher_user.id)
    db_session.add(subj)
    await db_session.flush()

    sess = VivaSession(student_id=student_user.id, subject_id=subj.id, status=SessionStatus.COMPLETED)
    db_session.add(sess)
    await db_session.commit()

    other_student_token = create_access_token(subject=other_student.id, role="student")
    unassigned_teacher_token = create_access_token(subject=unassigned_teacher.id, role="teacher")

    # Other student is forbidden (403)
    resp_other_student = await client.get(
        f"/api/v1/audio/{sess.id}/turn-1",
        headers={"Authorization": f"Bearer {other_student_token}"},
    )
    assert resp_other_student.status_code == 403

    # Unassigned teacher is forbidden (403)
    resp_unassigned_teacher = await client.get(
        f"/api/v1/audio/{sess.id}/turn-1",
        headers={"Authorization": f"Bearer {unassigned_teacher_token}"},
    )
    assert resp_unassigned_teacher.status_code == 403


@pytest.mark.asyncio
async def test_student_data_export_and_deletion(
    client: AsyncClient,
    student_user: User,
    teacher_user: User,
    db_session: AsyncSession,
):
    """WS-2.5: Students can export their full viva history and request complete account data deletion."""
    student_token = create_access_token(subject=student_user.id, role="student")

    # 1. Export data
    export_resp = await client.get(
        "/api/v1/auth/me/export-data",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "user_profile" in export_data
    assert "viva_examinations" in export_data
    assert export_data["user_profile"]["email"] == student_user.email

    # 2. Delete account data
    delete_resp = await client.delete(
        "/api/v1/auth/me/delete-account-data",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert delete_resp.status_code == 200

    # Verify user no longer exists in DB
    user_check = (await db_session.execute(select(User).where(User.id == student_user.id))).scalar_one_or_none()
    assert user_check is None


def test_cors_rejects_wildcard_origin() -> None:
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(CORS_ORIGINS="*", ENVIRONMENT="testing")


def test_production_rejects_demo_mode() -> None:
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="DEMO_MODE"):
        Settings(ENVIRONMENT="production", DEMO_MODE=True, SECRET_KEY="x" * 64)


async def test_cors_preflight_allows_only_configured_origin(client) -> None:
    ok = await client.options(
        "/api/v1/subjects",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    # Credentials are allowed (cookie session) only because the origin list is explicit.
    assert ok.headers.get("access-control-allow-credentials") == "true"

    evil = await client.options(
        "/api/v1/subjects",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in evil.headers


async def test_teachers_only_access_sessions_in_their_own_subjects(
    client, db_session, student_user, teacher_user
) -> None:
    from app.core.security import create_access_token, get_password_hash
    from app.models.session import SessionStatus, VivaSession
    from app.models.subject import Subject
    from app.models.user import User, UserRole

    other = User(
        email="other.teacher@vivaiq.edu",
        hashed_password=get_password_hash("OtherPass123!"),
        full_name="Other Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other)
    db_session.add(Subject(id="subj-own", name="OS", code="OWN1", description="", teacher_id=teacher_user.id))
    db_session.add(
        VivaSession(
            id="sess-own",
            student_id=student_user.id,
            subject_id="subj-own",
            status=SessionStatus.COMPLETED,
            recording_consent=True,
        )
    )
    await db_session.commit()

    owner = {"Authorization": f"Bearer {create_access_token(subject=teacher_user.id, role='teacher')}"}
    stranger = {"Authorization": f"Bearer {create_access_token(subject=other.id, role='teacher')}"}

    assert [s["id"] for s in (await client.get("/api/v1/sessions", headers=owner)).json()] == ["sess-own"]
    assert (await client.get("/api/v1/sessions", headers=stranger)).json() == []

    for method, url, body in [
        ("GET", "/api/v1/sessions/sess-own", None),
        ("GET", "/api/v1/sessions/sess-own/state", None),
        ("GET", "/api/v1/reports/sessions/sess-own", None),
        ("GET", "/api/v1/reports/sessions/sess-own/export/csv", None),
        ("POST", "/api/v1/reports/sessions/sess-own/notes", {"teacher_notes": "x"}),
        ("POST", "/api/v1/reports/sessions/sess-own/override", {"new_score": 1, "reason": "tampering"}),
    ]:
        resp = await client.request(method, url, headers=stranger, json=body)
        assert resp.status_code == 403, (url, resp.status_code)

    assert (await client.get("/api/v1/sessions/sess-own", headers=owner)).status_code == 200


async def test_document_management_requires_subject_ownership_and_purges_vectors(
    client, db_session, teacher_user, monkeypatch, tmp_path
) -> None:
    import app.api.documents as documents_api
    from app.core.security import create_access_token, get_password_hash
    from app.models.document import Document, IngestionStatus
    from app.models.subject import Subject
    from app.models.user import User, UserRole

    other = User(
        email="other2@vivaiq.edu",
        hashed_password=get_password_hash("OtherPass123!"),
        full_name="Other",
        role=UserRole.TEACHER,
        is_active=True,
    )
    stored = tmp_path / "notes.txt"
    stored.write_text("Deadlocks need four conditions.")
    db_session.add_all(
        [
            other,
            Subject(id="subj-docs", name="OS", code="DOC1", description="", teacher_id=teacher_user.id),
            Document(
                id="doc-1",
                subject_id="subj-docs",
                filename="notes.txt",
                file_path=str(stored),
                file_type="txt",
                file_size_bytes=10,
                ingestion_status=IngestionStatus.COMPLETED,
            ),
        ]
    )
    await db_session.commit()

    deleted: list = []

    class FakeStore:
        async def delete_document(self, subject_id: str, document_id: str) -> None:
            deleted.append((subject_id, document_id))

    monkeypatch.setattr(documents_api, "get_rag_store", lambda: FakeStore())
    stranger = {"Authorization": f"Bearer {create_access_token(subject=other.id, role='teacher')}"}
    owner = {"Authorization": f"Bearer {create_access_token(subject=teacher_user.id, role='teacher')}"}

    upload = await client.post(
        "/api/v1/subjects/subj-docs/documents", headers=stranger, files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert upload.status_code == 403
    assert (await client.delete("/api/v1/documents/doc-1", headers=stranger)).status_code == 403
    assert deleted == [] and stored.exists()

    assert (await client.delete("/api/v1/documents/doc-1", headers=owner)).status_code == 204
    assert deleted == [("subj-docs", "doc-1")]
    assert not stored.exists()
