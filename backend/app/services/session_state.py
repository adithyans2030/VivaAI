"""Viva Voce Session State Machine & Adaptive Orchestrator.

Manages session lifecycle (CREATED -> WARMUP -> IN_PROGRESS -> COMPLETED),
adaptive question sequencing, reconnect recovery, and end-of-session aggregation.
"""

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.session import AuthenticityLikelihood, SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.turn import Turn
from app.services.authenticity import AuthenticityReport, get_authenticity_analyzer
from app.services.examiner import ExaminerService, GeneratedQuestion, get_examiner_service
from app.services.grader import GraderResult, GraderService, get_grader_service


class VivaSessionOrchestrator:
    """Coordinates state transitions, turns, and evaluation for viva sessions."""

    def __init__(
        self,
        examiner: Optional[ExaminerService] = None,
        grader: Optional[GraderService] = None,
    ):
        self.examiner = examiner or get_examiner_service()
        self.grader = grader or get_grader_service()
        self.authenticity_analyzer = get_authenticity_analyzer()

    async def get_or_create_next_question(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> Tuple[Optional[Turn], bool]:
        """Determine next question for session. Returns (Turn, is_completed).

        If a question has already been generated for the active turn and is awaiting
        student answer, returns that existing Turn (for reconnect resilience).
        """
        stmt = (
            select(VivaSession)
            .where(VivaSession.id == session_id)
            .options(
                selectinload(VivaSession.subject),
                selectinload(VivaSession.turns),
            )
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        # Check for unfinished turn (reconnect scenario)
        for t in session.turns:
            if t.transcript is None or t.score_0_10 is None:
                logger.info(f"Session {session_id} resuming existing Turn {t.turn_number}")
                return t, False

        turns_count = len(session.turns)
        next_turn_number = turns_count + 1

        # Check completion condition
        if turns_count >= settings.MAX_QUESTIONS:
            await self.finalize_session(db, session)
            return None, True

        # Calculate running score and covered topics
        scored_turns = [t for t in session.turns if t.score_0_10 is not None]
        avg_score = (
            sum(t.score_0_10 for t in scored_turns) / len(scored_turns)
            if scored_turns
            else 7.0
        )
        covered_topics = [t.topic for t in session.turns if t.topic]

        # Check if previous turn requested a follow-up probe
        last_turn = session.turns[-1] if session.turns else None
        followup_context = None
        if last_turn and last_turn.followup_needed and last_turn.followup_type:
            followup_context = {
                "question": last_turn.question_text,
                "answer": last_turn.transcript or "",
                "type": last_turn.followup_type,
            }

        # Formulate next question adaptively
        subject_name = session.subject.name if session.subject else "General Topic"
        gen_q = await self.examiner.generate_question(
            subject_id=session.subject_id,
            subject_name=subject_name,
            turn_number=next_turn_number,
            covered_topics=covered_topics,
            current_running_score=avg_score,
            followup_context=followup_context,
        )

        # Update session status
        if next_turn_number == 1:
            session.status = SessionStatus.WARMUP
        else:
            session.status = SessionStatus.IN_PROGRESS

        # Create new Turn in DB
        new_turn = Turn(
            session_id=session.id,
            turn_number=next_turn_number,
            question_text=gen_q.question_text,
            question_type=gen_q.question_type,
            topic=gen_q.topic,
            source_references=gen_q.source_references,
            prompt_version=self.examiner.prompt_version,
        )
        db.add(new_turn)
        await db.commit()
        await db.refresh(new_turn)

        return new_turn, False

    async def evaluate_turn_submission(
        self,
        db: AsyncSession,
        session_id: str,
        turn_id: str,
        student_transcript: str,
        word_timestamps: List[Dict[str, Any]],
        audio_path: Optional[str] = None,
        audio_duration_seconds: Optional[float] = None,
        onset_latency_seconds: Optional[float] = None,
    ) -> Tuple[Turn, GraderResult, AuthenticityReport]:
        """Grade student answer, compute advisory authenticity metrics, and update DB."""
        sess_stmt = (
            select(VivaSession)
            .where(VivaSession.id == session_id)
            .options(
                selectinload(VivaSession.subject),
                selectinload(VivaSession.turns),
            )
        )
        session = (await db.execute(sess_stmt)).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        turn_stmt = select(Turn).where(Turn.id == turn_id)
        turn = (await db.execute(turn_stmt)).scalar_one_or_none()
        if not turn:
            raise ValueError(f"Turn {turn_id} not found.")

        # Update transcript & audio metadata
        turn.transcript = student_transcript
        turn.word_timestamps = word_timestamps
        turn.student_audio_path = audio_path
        turn.audio_duration_seconds = audio_duration_seconds

        # 1. Rubric Grading via LLM
        expected_points = [
            ref.get("text", "") for ref in (turn.source_references or [])
        ]
        grade_res = await self.grader.grade_answer(
            subject_name=session.subject.name if session.subject else "Subject",
            question_text=turn.question_text,
            student_answer=student_transcript,
            expected_key_points=expected_points,
        )

        turn.score_0_10 = grade_res.score_0_10
        turn.rubric_breakdown = grade_res.rubric.model_dump()
        turn.feedback = grade_res.feedback
        turn.followup_needed = grade_res.followup_needed
        turn.followup_type = grade_res.followup_type

        # 2. Advisory Authenticity Analysis (Strictly non-punitive)
        reference_chunks = [ref.get("text", "") for ref in (turn.source_references or [])]
        core_turns = [t for t in session.turns if t.question_type == "conceptual" and t.score_0_10 is not None]
        core_avg = (
            sum(t.score_0_10 for t in core_turns) / len(core_turns)
            if core_turns
            else None
        )

        auth_report = self.authenticity_analyzer.analyze_turn(
            turn_number=turn.turn_number,
            student_text=student_transcript,
            reference_chunks=reference_chunks,
            word_timestamps=word_timestamps,
            onset_latency_seconds=onset_latency_seconds,
            audio_duration_seconds=audio_duration_seconds,
            question_type=turn.question_type,
            core_avg_score=core_avg,
            turn_score=turn.score_0_10,
        )

        turn.authenticity_likelihood = auth_report.likelihood
        turn.authenticity_confidence = auth_report.confidence
        turn.authenticity_reasons = auth_report.reasons
        turn.speech_features = {
            "composite_risk_score": auth_report.composite_risk_score_0_1,
            "signals": {k: v.model_dump() for k, v in auth_report.signals.items()},
        }

        # If warmup turn, record acoustic baseline in session
        if turn.turn_number == 1 and not session.warmup_baseline:
            session.warmup_baseline = {
                "onset_latency": onset_latency_seconds,
                "duration": audio_duration_seconds,
                "disfluency_rate": auth_report.signals.get("disfluency_rate", {}).raw_value if "disfluency_rate" in auth_report.signals else 2.0,
            }

        await db.commit()
        await db.refresh(turn)

        return turn, grade_res, auth_report

    async def finalize_session(
        self,
        db: AsyncSession,
        session: VivaSession,
    ) -> Dict[str, Any]:
        """Compute aggregated scores, authenticity summary, and finalize session."""
        session.status = SessionStatus.COMPLETED

        scored_turns = [t for t in session.turns if t.score_0_10 is not None]
        if scored_turns:
            total_score = sum(t.score_0_10 for t in scored_turns) / len(scored_turns)
            session.total_score = round(total_score, 2)
        else:
            session.total_score = 0.0

        # Aggregate Authenticity Reports
        turn_reports = []
        for t in session.turns:
            if t.speech_features and "signals" in t.speech_features:
                from app.services.authenticity import SignalScore
                signals_dict = {
                    k: SignalScore(**v) for k, v in t.speech_features["signals"].items()
                }
                turn_reports.append(
                    AuthenticityReport(
                        likelihood=t.authenticity_likelihood,
                        confidence=t.authenticity_confidence or 0.8,
                        composite_risk_score_0_1=t.speech_features.get("composite_risk_score", 0.0),
                        reasons=t.authenticity_reasons or [],
                        signals=signals_dict,
                    )
                )

        agg_auth = self.authenticity_analyzer.aggregate_session(turn_reports)
        session.overall_authenticity_likelihood = agg_auth.likelihood
        session.overall_authenticity_confidence = agg_auth.confidence
        session.overall_authenticity_reasons = agg_auth.reasons

        # Construct Final Report for Teacher
        final_report = {
            "session_id": session.id,
            "student_id": session.student_id,
            "subject_id": session.subject_id,
            "status": session.status.value,
            "total_score": session.total_score,
            "turns_count": len(session.turns),
            "authenticity": {
                "likelihood": session.overall_authenticity_likelihood.value,
                "confidence": session.overall_authenticity_confidence,
                "reasons": session.overall_authenticity_reasons,
                "is_advisory": True,
            },
            "turn_summaries": [
                {
                    "turn_number": t.turn_number,
                    "question_text": t.question_text,
                    "question_type": t.question_type,
                    "student_transcript": t.transcript,
                    "score_0_10": t.score_0_10,
                    "feedback": t.feedback,
                    "authenticity_likelihood": t.authenticity_likelihood.value,
                }
                for t in session.turns
            ],
        }
        session.final_report = final_report

        await db.commit()
        return final_report

    async def get_recovery_state(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> Dict[str, Any]:
        """Fetch comprehensive session state for client reconnection recovery."""
        stmt = (
            select(VivaSession)
            .where(VivaSession.id == session_id)
            .options(
                selectinload(VivaSession.subject),
                selectinload(VivaSession.turns),
            )
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        # Find active question
        active_turn = None
        for t in session.turns:
            if t.transcript is None or t.score_0_10 is None:
                active_turn = t
                break

        return {
            "session_id": session.id,
            "status": session.status.value,
            "recording_consent": session.recording_consent,
            "subject": {
                "id": session.subject.id if session.subject else None,
                "name": session.subject.name if session.subject else "Subject",
            },
            "active_turn": {
                "turn_id": active_turn.id,
                "turn_number": active_turn.turn_number,
                "question_text": active_turn.question_text,
                "question_type": active_turn.question_type,
            } if active_turn else None,
            "turns_completed": len([t for t in session.turns if t.score_0_10 is not None]),
            "total_turns": len(session.turns),
            "max_questions": settings.MAX_QUESTIONS,
            "history": [
                {
                    "turn_id": t.id,
                    "turn_number": t.turn_number,
                    "question_text": t.question_text,
                    "student_transcript": t.transcript,
                    "score_0_10": t.score_0_10,
                    "feedback": t.feedback,
                }
                for t in session.turns
                if t.score_0_10 is not None
            ],
        }


_orchestrator: Optional[VivaSessionOrchestrator] = None


def get_viva_orchestrator() -> VivaSessionOrchestrator:
    """Singleton factory for VivaSessionOrchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VivaSessionOrchestrator()
    return _orchestrator
