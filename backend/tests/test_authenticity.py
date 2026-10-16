"""Tests for Advisory Authenticity Assessment Engine."""

import pytest
from app.models.session import AuthenticityLikelihood
from app.services.authenticity import (
    AuthenticityAnalyzer,
    AuthenticityReport,
    get_authenticity_analyzer,
)


@pytest.fixture
def analyzer() -> AuthenticityAnalyzer:
    return get_authenticity_analyzer()


def test_spontaneous_answer_analysis(analyzer: AuthenticityAnalyzer):
    """Spontaneous, conversational answer with natural pauses and paraphrasing."""
    transcript = (
        "Well, um, so the deadlock basically happens when four conditions are met at the same time. "
        "First is mutual exclusion, meaning, uh, only one thread can hold a resource at once. "
        "And then hold and wait, like where you hold something while asking for another thing. "
        "There is no preemption, and, um, finally circular wait."
    )
    reference = [
        "Deadlock occurs when four Coffman conditions hold: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait."
    ]
    timestamps = [
        {"word": "Well,", "start": 1.2, "end": 1.5},
        {"word": "um,", "start": 1.6, "end": 1.9},
        {"word": "so", "start": 2.0, "end": 2.2},
        {"word": "the", "start": 2.2, "end": 2.4},
        {"word": "deadlock", "start": 2.4, "end": 2.9},
    ]

    report = analyzer.analyze_turn(
        turn_number=2,
        student_text=transcript,
        reference_chunks=reference,
        word_timestamps=timestamps,
        onset_latency_seconds=1.8,
        question_type="conceptual",
    )

    assert isinstance(report, AuthenticityReport)
    assert report.is_advisory is True
    assert report.likelihood == AuthenticityLikelihood.LOW
    assert report.composite_risk_score_0_1 < 0.35
    assert "disclaimer" in report.model_dump()


def test_scripted_reading_answer_analysis(analyzer: AuthenticityAnalyzer):
    """Scripted note-reading with verbatim phrasing, 0 fillers, and instant onset."""
    transcript = (
        "Deadlock occurs when four Coffman conditions hold simultaneously: "
        "Mutual Exclusion wherein at least one resource is held in a non-shareable mode; "
        "Hold and Wait where a process must be holding at least one resource and requesting additional resources; "
        "No Preemption; and Circular Wait."
    )
    reference = [
        "Deadlock occurs when four Coffman conditions hold simultaneously: Mutual Exclusion wherein at least one resource is held in a non-shareable mode; Hold and Wait where a process must be holding at least one resource and requesting additional resources; No Preemption; and Circular Wait."
    ]

    report = analyzer.analyze_turn(
        turn_number=3,
        student_text=transcript,
        reference_chunks=reference,
        word_timestamps=[],
        onset_latency_seconds=0.2,  # Suspiciously fast onset
        question_type="conceptual",
    )

    assert report.is_advisory is True
    assert report.likelihood in (AuthenticityLikelihood.HIGH, AuthenticityLikelihood.MEDIUM)
    assert report.composite_risk_score_0_1 >= 0.35
    assert len(report.reasons) > 0
    # Signals checked
    assert "ngram_overlap" in report.signals
    assert report.signals["ngram_overlap"].flagged is True


def test_dynamic_probe_delta(analyzer: AuthenticityAnalyzer):
    """Verifies that high drop between core question and probe triggers an explanation."""
    report = analyzer.analyze_turn(
        turn_number=4,
        student_text="I am not really sure how that would apply here.",
        reference_chunks=[],
        question_type="probe",
        core_avg_score=9.5,
        turn_score=3.0,
    )

    assert "probe_delta" in report.signals
    assert report.signals["probe_delta"].flagged is True
    assert any("divergence" in r.lower() for r in report.reasons)


def test_session_aggregation(analyzer: AuthenticityAnalyzer):
    """Verifies session-level aggregation over multiple turns."""
    r1 = analyzer.analyze_turn(1, "Hello, my name is Alex.", [], question_type="warmup")
    r2 = analyzer.analyze_turn(2, "Virtual memory uses page tables.", ["Virtual memory uses page tables to map virtual addresses to physical frames."])

    agg = analyzer.aggregate_session([r1, r2])
    assert isinstance(agg, AuthenticityReport)
    assert agg.is_advisory is True
    assert agg.likelihood in (AuthenticityLikelihood.LOW, AuthenticityLikelihood.MEDIUM)
