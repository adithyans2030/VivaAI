"""Tests for Viva Voce Session State Machine, Adaptive Orchestrator, and Reconnect State."""

import pytest
from starlette.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.session import AuthenticityLikelihood, SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.user import User
from app.services.examiner import ExaminerService
from app.services.grader import GraderService
from app.services.llm.mock import MockLLMProvider
from app.services.session_state import VivaSessionOrchestrator
from tests.conftest import test_async_session


@pytest.fixture
def mock_orchestrator() -> VivaSessionOrchestrator:
    examiner = ExaminerService(prompt_version="v1", llm_provider=MockLLMProvider())
    grader = GraderService(prompt_version="v1", llm_provider=MockLLMProvider())
    return VivaSessionOrchestrator(examiner=examiner, grader=grader)


@pytest.mark.asyncio
async def test_session_state_machine_flow(student_user: User, mock_orchestrator: VivaSessionOrchestrator):
    """Test full cycle: created -> warmup -> core -> finalize."""
    async with test_async_session() as db:
        # 1. Create subject & session
        subject = Subject(
            id="cs302-test",
            name="Distributed Systems",
            code="CS302",
            description="Consensus and Paxos",
            teacher_id="teacher-id",
        )
        session = VivaSession(
            id="sess-state-1",
            student_id=student_user.id,
            subject_id=subject.id,
            status=SessionStatus.CREATED,
            recording_consent=True,
        )
        db.add(subject)
        db.add(session)
        await db.commit()

        # 2. Turn 1 (Warmup)
        t1, is_done = await mock_orchestrator.get_or_create_next_question(db, session.id)
        assert is_done is False
        assert t1 is not None
        assert t1.turn_number == 1
        assert t1.question_type == "warmup"

        # Re-fetch session to verify status changed to WARMUP
        await db.refresh(session)
        assert session.status == SessionStatus.WARMUP

        # Evaluate Turn 1 submission
        t1_evaluated, grade1, auth1 = await mock_orchestrator.evaluate_turn_submission(
            db=db,
            session_id=session.id,
            turn_id=t1.id,
            student_transcript="Hello, my name is Alex and I studied Raft consensus.",
            word_timestamps=[{"word": "Hello", "start": 0.5, "end": 0.9}],
            audio_duration_seconds=3.2,
            onset_latency_seconds=1.2,
        )
        assert t1_evaluated.score_0_10 is not None
        assert t1_evaluated.authenticity_likelihood is not None

        # 3. Turn 2 (Core question)
        t2, is_done2 = await mock_orchestrator.get_or_create_next_question(db, session.id)
        assert is_done2 is False
        assert t2.turn_number == 2
        await db.refresh(session)
        assert session.status == SessionStatus.IN_PROGRESS

        # 4. Reconnect test: fetching recovery state
        state = await mock_orchestrator.get_recovery_state(db, session.id)
        assert state["session_id"] == session.id
        assert state["status"] == SessionStatus.IN_PROGRESS.value
        assert state["turns_completed"] == 1
        assert state["active_turn"]["turn_number"] == 2
        assert len(state["history"]) == 1

        # 5. Finalize session
        final_report = await mock_orchestrator.finalize_session(db, session)
        assert session.status == SessionStatus.COMPLETED
        assert session.total_score is not None
        assert session.overall_authenticity_likelihood in (
            AuthenticityLikelihood.LOW,
            AuthenticityLikelihood.MEDIUM,
            AuthenticityLikelihood.HIGH,
        )
        assert "authenticity" in final_report


def test_session_state_http_endpoint(student_user: User, teacher_user: User, monkeypatch):
    """Test HTTP GET /api/v1/sessions/{id}/state recovery endpoint."""

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

    try:
        with TestClient(app) as client:
            # Create subject
            subj_resp = client.post(
                "/api/v1/subjects",
                headers={"Authorization": f"Bearer {teacher_token}"},
                json={"name": "Database Systems", "code": "CS401", "description": "ACID and Indexing"},
            )
            assert subj_resp.status_code == 201
            subject_id = subj_resp.json()["id"]

            # Create session
            sess_resp = client.post(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {student_token}"},
                json={"subject_id": subject_id},
            )
            assert sess_resp.status_code == 201
            session_id = sess_resp.json()["id"]

            # Query recovery state
            state_resp = client.get(
                f"/api/v1/sessions/{session_id}/state",
                headers={"Authorization": f"Bearer {student_token}"},
            )
            assert state_resp.status_code == 200
            state = state_resp.json()
            assert state["session_id"] == session_id
            assert state["status"] == "created"
            assert state["turns_completed"] == 0
    finally:
        app.dependency_overrides.clear()
