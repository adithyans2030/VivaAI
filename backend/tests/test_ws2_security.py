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

from app.core.security import consume_ws_ticket, create_access_token, decode_token
from app.models.session import SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.user import User, UserRole


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
    record = consume_ws_ticket(ticket, sess.id)
    assert record["user_id"] == student_user.id

    # Second consumption fails (single-use guarantee)
    with pytest.raises(ValueError, match="already been used"):
        consume_ws_ticket(ticket, sess.id)


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

    student_token = create_access_token(subject=student_user.id, role="student")
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
