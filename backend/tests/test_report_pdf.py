"""PDF session report: content, advisory labelling, font fallback and access control."""

import io
from datetime import datetime, timezone

import pytest
from pypdf import PdfReader

from app.core.security import create_access_token, get_password_hash
from app.models.session import AuthenticityLikelihood, SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.turn import Turn
from app.models.user import User, UserRole
from app.services import report_pdf


def _text(pdf_bytes: bytes) -> str:
    raw = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages)
    return " ".join(raw.split())  # justified lines extract with doubled spaces


def _session() -> tuple:
    student = User(id="s1", email="s@x.edu", full_name="Asha Rao", hashed_password="x", role=UserRole.STUDENT)
    subject = Subject(id="sub1", name="Operating Systems", code="CS301", description="", teacher_id="t1")
    session = VivaSession(
        id="sess-pdf",
        student_id="s1",
        subject_id="sub1",
        status=SessionStatus.COMPLETED,
        recording_consent=True,
        total_score=7.5,
        overall_authenticity_likelihood=AuthenticityLikelihood.MEDIUM,
        overall_authenticity_confidence=0.62,
        overall_authenticity_reasons=["High verbatim overlap with course notes on Q1."],
        teacher_notes="Discussed Q1 in person; student explained it well.",
        created_at=datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc),
    )
    session.student, session.subject = student, subject
    turns = [
        Turn(
            session_id="sess-pdf",
            turn_number=1,
            question_text="What are the four Coffman conditions?",
            question_type="conceptual",
            topic="Deadlocks",
            prompt_version="v1",
            transcript="Mutual exclusion, hold and wait, no preemption, circular wait. नमस्ते",
            score_0_10=8.0,
            rubric_breakdown={"correctness": 8, "completeness": 8, "clarity": 7, "depth": 6, "missing_points": []},
            feedback="Complete list.",
            authenticity_likelihood=AuthenticityLikelihood.MEDIUM,
            authenticity_confidence=0.6,
            authenticity_reasons=["Matches textbook wording closely."],
            source_references=[{"source": "os_notes.pdf", "page": 12}],
        ),
        Turn(
            session_id="sess-pdf",
            turn_number=2,
            question_text="Give an example not in the book.",
            question_type="probe",
            topic="Deadlocks",
            prompt_version="v1",
            transcript=None,
            authenticity_likelihood=AuthenticityLikelihood.UNKNOWN,
        ),
    ]
    return session, turns


def test_pdf_contains_report_and_advisory_labels() -> None:
    session, turns = _session()
    text = _text(report_pdf.build_session_pdf(session, turns))

    for expected in [
        "Asha Rao",
        "CS301: Operating Systems",
        "7.5 / 10",
        "Advisory authenticity: MEDIUM",
        "ADVISORY ONLY",
        "Discussed Q1 in person",
        "Q1. What are the four Coffman conditions?",
        "os_notes.pdf (p. 12)",
        "Not answered",
        "Not graded",
    ]:
        assert expected in text, expected


def test_pdf_without_unicode_font_replaces_unsupported_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_pdf, "_find_font", lambda: None)
    session, turns = _session()
    text = _text(report_pdf.build_session_pdf(session, turns))
    assert "circular wait" in text and "नमस्ते" not in text


async def test_pdf_endpoint_enforces_session_access(client, db_session, student_user, teacher_user) -> None:
    other = User(
        email="pdf.other@vivaiq.edu",
        hashed_password=get_password_hash("OtherPass123!"),
        full_name="Other",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add_all(
        [
            other,
            Subject(id="subj-pdf", name="OS", code="PDF1", description="", teacher_id=teacher_user.id),
            VivaSession(
                id="sess-pdf-api",
                student_id=student_user.id,
                subject_id="subj-pdf",
                status=SessionStatus.COMPLETED,
                recording_consent=True,
            ),
        ]
    )
    await db_session.commit()

    def auth(user: User) -> dict:
        return {"Authorization": f"Bearer {create_access_token(subject=user.id, role=user.role.value)}"}

    url = "/api/v1/reports/sessions/sess-pdf-api/export/pdf"
    ok = await client.get(url, headers=auth(teacher_user))
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "application/pdf"
    assert ok.content.startswith(b"%PDF")

    assert (await client.get(url, headers=auth(other))).status_code == 403
    assert (await client.get(url, headers=auth(student_user))).status_code == 403
