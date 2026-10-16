"""Advisory & Explainable Authenticity Assessment Engine.

Analyzes oral responses across 6 acoustic and linguistic signals to detect
potential note-reading vs. spontaneous explanation. Strictly advisory;
zero automated penalties. Flags are for teacher review only.
"""

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.models.session import AuthenticityLikelihood


class SignalScore(BaseModel):
    """Detailed score for an individual authenticity signal."""
    name: str
    raw_value: float
    normalized_score_0_1: float  # 0.0 = highly spontaneous, 1.0 = highly scripted/reading
    threshold: float
    flagged: bool
    explanation: str


class AuthenticityReport(BaseModel):
    """Structured advisory authenticity assessment for a turn or session."""
    likelihood: AuthenticityLikelihood
    confidence: float = Field(ge=0.0, le=1.0)
    composite_risk_score_0_1: float = Field(ge=0.0, le=1.0)
    reasons: List[str]
    signals: Dict[str, SignalScore]
    is_advisory: bool = True
    disclaimer: str = (
        "This assessment is strictly advisory and heuristic-based. "
        "It must never be used to penalize a student automatically. "
        "Review audio recordings and context before drawing conclusions."
    )


class AuthenticityAnalyzer:
    """Analyzes student viva turns using 6 explainable acoustic and linguistic signals."""

    # Natural speech fillers and disfluency markers
    FILLERS: List[str] = [
        "um", "uh", "er", "ah", "like", "you know", "i mean", "sort of",
        "kind of", "actually", "basically", "well", "so yeah",
    ]

    def __init__(
        self,
        ngram_threshold: float = 0.40,
        disfluency_min_expected: float = 1.0,  # Fillers per 100 words in spontaneous speech
        midclause_pause_ratio_threshold: float = 0.35,
        onset_latency_lower_sec: float = 0.4,
        onset_latency_upper_sec: float = 7.0,
        probe_score_delta_threshold: float = 3.5,
    ):
        self.ngram_threshold = ngram_threshold
        self.disfluency_min_expected = disfluency_min_expected
        self.midclause_pause_ratio_threshold = midclause_pause_ratio_threshold
        self.onset_latency_lower_sec = onset_latency_lower_sec
        self.onset_latency_upper_sec = onset_latency_upper_sec
        self.probe_score_delta_threshold = probe_score_delta_threshold

    # -------------------------------------------------------------------------
    # Signal 1: Verbatim N-gram Overlap vs RAG Knowledge Base Chunks
    # -------------------------------------------------------------------------
    def compute_ngram_overlap(
        self,
        student_text: str,
        reference_chunks: List[str],
        n: int = 3,
    ) -> SignalScore:
        """Calculate n-gram overlap between student answer and reference course materials."""
        student_words = [re.sub(r"[^\w]", "", w.lower()) for w in student_text.split() if w.strip()]
        if len(student_words) < n or not reference_chunks:
            return SignalScore(
                name="ngram_overlap",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=self.ngram_threshold,
                flagged=False,
                explanation="Insufficient answer length or reference material for n-gram comparison.",
            )

        student_ngrams = set(
            tuple(student_words[i : i + n])
            for i in range(len(student_words) - n + 1)
        )

        all_ref_ngrams = set()
        for chunk in reference_chunks:
            ref_words = [re.sub(r"[^\w]", "", w.lower()) for w in chunk.split() if w.strip()]
            for i in range(len(ref_words) - n + 1):
                all_ref_ngrams.add(tuple(ref_words[i : i + n]))

        if not student_ngrams or not all_ref_ngrams:
            overlap_ratio = 0.0
        else:
            intersection = student_ngrams.intersection(all_ref_ngrams)
            overlap_ratio = len(intersection) / len(student_ngrams)

        norm_score = min(1.0, overlap_ratio / max(0.01, self.ngram_threshold * 1.5))
        flagged = overlap_ratio >= self.ngram_threshold
        pct = round(overlap_ratio * 100, 1)

        explanation = (
            f"High verbatim phrase matching ({pct}% {n}-gram overlap with course materials). "
            f"Phrasing closely mirrors reference text."
            if flagged
            else f"Natural phrasing ({pct}% {n}-gram overlap with course materials)."
        )

        return SignalScore(
            name="ngram_overlap",
            raw_value=overlap_ratio,
            normalized_score_0_1=norm_score,
            threshold=self.ngram_threshold,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 2: Disfluency Rate (Spontaneous Hesitations vs Scripted Flow)
    # -------------------------------------------------------------------------
    def compute_disfluency_rate(
        self,
        student_text: str,
        word_timestamps: Optional[List[Dict[str, Any]]] = None,
    ) -> SignalScore:
        """Natural spontaneous speech contains ~1.5 - 5.0 fillers/restarts per 100 words.
        Verbatim reading from prepared notes displays unnaturally continuous fluency.
        """
        words = [re.sub(r"[^\w]", "", w.lower()) for w in student_text.split() if w.strip()]
        total_words = len(words)
        if total_words < 10:
            return SignalScore(
                name="disfluency_rate",
                raw_value=2.0,
                normalized_score_0_1=0.0,
                threshold=self.disfluency_min_expected,
                flagged=False,
                explanation="Short answer, baseline disfluency assumed normal.",
            )

        lower_text = f" {student_text.lower()} "
        filler_count = 0
        for filler in self.FILLERS:
            pattern = rf"\b{re.escape(filler)}\b"
            filler_count += len(re.findall(pattern, lower_text))

        # Check for adjacent word repetitions ("the the", "we we", "is is")
        for i in range(len(words) - 1):
            if words[i] == words[i + 1] and len(words[i]) > 1:
                filler_count += 1

        rate_per_100 = (filler_count / total_words) * 100.0

        # Unusually low disfluency (< 0.5 per 100 words) in complex answers is suspicious
        if rate_per_100 < self.disfluency_min_expected and total_words >= 30:
            flagged = True
            norm_score = max(0.0, 1.0 - (rate_per_100 / self.disfluency_min_expected))
            explanation = (
                f"Unusually polished fluency ({rate_per_100:.1f} disfluencies/100 words, "
                f"expected >= {self.disfluency_min_expected}). Speech displays reading cadence."
            )
        else:
            flagged = False
            norm_score = 0.0
            explanation = (
                f"Natural conversational disfluency rate ({rate_per_100:.1f} per 100 words)."
            )

        return SignalScore(
            name="disfluency_rate",
            raw_value=rate_per_100,
            normalized_score_0_1=norm_score,
            threshold=self.disfluency_min_expected,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 3: Pause Pattern Distribution (Syntactic vs Mid-Clause Pauses)
    # -------------------------------------------------------------------------
    def compute_pause_distribution(
        self,
        word_timestamps: Optional[List[Dict[str, Any]]],
    ) -> SignalScore:
        """Analyzes word-level pause distribution.
        Natural speech pauses cluster at clause/sentence boundaries.
        Note-reading pauses occur mid-phrase during visual scanning.
        """
        if not word_timestamps or len(word_timestamps) < 6:
            return SignalScore(
                name="pause_distribution",
                raw_value=0.15,
                normalized_score_0_1=0.0,
                threshold=self.midclause_pause_ratio_threshold,
                flagged=False,
                explanation="Insufficient word timestamp data for pause boundary analysis.",
            )

        pauses: List[Tuple[float, str, str]] = []
        for i in range(len(word_timestamps) - 1):
            curr_end = word_timestamps[i].get("end", 0.0)
            next_start = word_timestamps[i + 1].get("start", 0.0)
            gap = next_start - curr_end
            if gap >= 0.4:  # noticeable pause > 400ms
                curr_word = word_timestamps[i].get("word", "")
                next_word = word_timestamps[i + 1].get("word", "")
                pauses.append((gap, curr_word, next_word))

        if not pauses:
            return SignalScore(
                name="pause_distribution",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=self.midclause_pause_ratio_threshold,
                flagged=False,
                explanation="Fluid speech with no atypical hesitations.",
            )

        mid_clause_pauses = 0
        punctuation_marks = (".", ",", ";", ":", "?", "!", "-", "—")

        for gap, curr_word, next_word in pauses:
            # If pause does not follow punctuation or conjunction, classify as mid-clause
            is_boundary = any(curr_word.strip().endswith(p) for p in punctuation_marks)
            is_boundary = is_boundary or next_word.strip().lower() in ("and", "but", "however", "because", "so", "or")
            if not is_boundary:
                mid_clause_pauses += 1

        mid_clause_ratio = mid_clause_pauses / len(pauses)
        flagged = mid_clause_ratio >= self.midclause_pause_ratio_threshold and len(pauses) >= 3
        norm_score = min(1.0, mid_clause_ratio / max(0.01, self.midclause_pause_ratio_threshold * 1.5))

        explanation = (
            f"Frequent mid-clause pauses ({mid_clause_ratio * 100:.1f}% of pauses occurred mid-phrase), "
            f"suggestive of visual scanning or reading."
            if flagged
            else f"Normal syntactic pause distribution ({mid_clause_ratio * 100:.1f}% mid-clause)."
        )

        return SignalScore(
            name="pause_distribution",
            raw_value=mid_clause_ratio,
            normalized_score_0_1=norm_score,
            threshold=self.midclause_pause_ratio_threshold,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 4: Prosody and Speaking Rate Variance
    # -------------------------------------------------------------------------
    def compute_prosody_variance(
        self,
        word_timestamps: Optional[List[Dict[str, Any]]],
        audio_duration_seconds: Optional[float] = None,
    ) -> SignalScore:
        """Assesses expressive variation in speech rate.
        Reading notes produces rigid, metronomic cadence with low variance.
        Spontaneous speech alternates between rapid bursts and slow contemplative phases.
        """
        if not word_timestamps or len(word_timestamps) < 10:
            return SignalScore(
                name="prosody_variance",
                raw_value=0.5,
                normalized_score_0_1=0.0,
                threshold=0.15,
                flagged=False,
                explanation="Standard conversational cadence.",
            )

        # Compute durations of consecutive 3-word windows
        durations = []
        for i in range(len(word_timestamps) - 2):
            t_start = word_timestamps[i].get("start", 0.0)
            t_end = word_timestamps[i + 2].get("end", 0.0)
            dur = max(0.1, t_end - t_start)
            durations.append(dur)

        if not durations:
            return SignalScore(
                name="prosody_variance",
                raw_value=0.5,
                normalized_score_0_1=0.0,
                threshold=0.15,
                flagged=False,
                explanation="Standard conversational cadence.",
            )

        mean_dur = sum(durations) / len(durations)
        variance = sum((d - mean_dur) ** 2 for d in durations) / len(durations)
        coeff_of_variation = math.sqrt(variance) / max(0.01, mean_dur)

        # Low coefficient of variation indicates robotic / metronomic reading
        flagged = coeff_of_variation < 0.18 and len(durations) >= 8
        norm_score = max(0.0, 1.0 - (coeff_of_variation / 0.25)) if flagged else 0.0

        explanation = (
            f"Low cadence variability (CV = {coeff_of_variation:.2f}). "
            f"Monotone or rhythmic reading pattern observed."
            if flagged
            else f"Natural expressive rhythm with healthy variation (CV = {coeff_of_variation:.2f})."
        )

        return SignalScore(
            name="prosody_variance",
            raw_value=coeff_of_variation,
            normalized_score_0_1=norm_score,
            threshold=0.18,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 5: Response Onset Latency
    # -------------------------------------------------------------------------
    def compute_onset_latency(
        self,
        onset_latency_seconds: Optional[float],
        question_type: str = "conceptual",
    ) -> SignalScore:
        """Evaluates elapsed time between question finish and student start.
        - Instant recitation (< 0.4s) on complex questions: memorized / reading script.
        - Protracted silence (> 7.0s) followed by burst of speed: locating answer in notes.
        """
        if onset_latency_seconds is None or onset_latency_seconds < 0:
            return SignalScore(
                name="onset_latency",
                raw_value=1.5,
                normalized_score_0_1=0.0,
                threshold=self.onset_latency_lower_sec,
                flagged=False,
                explanation="Onset latency within normal range.",
            )

        flagged = False
        norm_score = 0.0
        explanation = f"Natural response onset latency ({onset_latency_seconds:.1f}s)."

        # Instantaneous recitation on complex question
        if onset_latency_seconds < self.onset_latency_lower_sec and question_type != "warmup":
            flagged = True
            norm_score = 0.65
            explanation = (
                f"Extremely rapid onset latency ({onset_latency_seconds:.2f}s for a {question_type} question). "
                f"Immediate response without typical cognitive formulation pause."
            )
        # Visual search delay
        elif onset_latency_seconds > self.onset_latency_upper_sec:
            flagged = True
            norm_score = 0.50
            explanation = (
                f"Long delay before speaking ({onset_latency_seconds:.1f}s), "
                f"suggesting potential reference material consultation."
            )

        return SignalScore(
            name="onset_latency",
            raw_value=onset_latency_seconds,
            normalized_score_0_1=norm_score,
            threshold=self.onset_latency_lower_sec,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 6: Dynamic Probe Score Delta
    # -------------------------------------------------------------------------
    def compute_probe_delta(
        self,
        core_avg_score: Optional[float],
        probe_score: Optional[float],
    ) -> SignalScore:
        """Measures discrepancy between scripted conceptual questions vs unexpected probe.
        If a student scores 9.5 on core textbook questions but drops to 3.0 when probed
        with a counter-example or 'explain with an analogy', this indicates rote or reading.
        """
        if core_avg_score is None or probe_score is None:
            return SignalScore(
                name="probe_delta",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=self.probe_score_delta_threshold,
                flagged=False,
                explanation="No probe comparison available.",
            )

        delta = max(0.0, core_avg_score - probe_score)
        flagged = delta >= self.probe_score_delta_threshold
        norm_score = min(1.0, delta / 6.0)

        explanation = (
            f"Significant performance divergence ({delta:.1f} pt drop between core and probe questions). "
            f"Strong textbook performance but difficulty applying concepts spontaneously."
            if flagged
            else f"Consistent conceptual understanding across core and probe questions (delta: {delta:.1f} pts)."
        )

        return SignalScore(
            name="probe_delta",
            raw_value=delta,
            normalized_score_0_1=norm_score,
            threshold=self.probe_score_delta_threshold,
            flagged=flagged,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Composite Assessment for a Single Turn
    # -------------------------------------------------------------------------
    def analyze_turn(
        self,
        turn_number: int,
        student_text: str,
        reference_chunks: List[str],
        word_timestamps: Optional[List[Dict[str, Any]]] = None,
        onset_latency_seconds: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        question_type: str = "conceptual",
        core_avg_score: Optional[float] = None,
        turn_score: Optional[float] = None,
    ) -> AuthenticityReport:
        """Run all applicable authenticity checks on a student's oral turn."""
        signals: Dict[str, SignalScore] = {}

        # 1. N-gram overlap
        s1 = self.compute_ngram_overlap(student_text, reference_chunks)
        signals["ngram_overlap"] = s1

        # 2. Disfluency rate
        s2 = self.compute_disfluency_rate(student_text, word_timestamps)
        signals["disfluency_rate"] = s2

        # 3. Pause distribution
        s3 = self.compute_pause_distribution(word_timestamps)
        signals["pause_distribution"] = s3

        # 4. Prosody / cadence variance
        s4 = self.compute_prosody_variance(word_timestamps, audio_duration_seconds)
        signals["prosody_variance"] = s4

        # 5. Onset latency
        s5 = self.compute_onset_latency(onset_latency_seconds, question_type)
        signals["onset_latency"] = s5

        # 6. Probe delta (if this turn is a probe)
        if question_type == "probe" and core_avg_score is not None and turn_score is not None:
            s6 = self.compute_probe_delta(core_avg_score, turn_score)
            signals["probe_delta"] = s6

        # Signal Weights (sum to 1.0)
        weights = {
            "ngram_overlap": 0.35,
            "disfluency_rate": 0.20,
            "pause_distribution": 0.15,
            "prosody_variance": 0.10,
            "onset_latency": 0.10,
            "probe_delta": 0.10,
        }

        active_weight = 0.0
        weighted_sum = 0.0
        reasons: List[str] = []

        for name, score in signals.items():
            w = weights.get(name, 0.10)
            weighted_sum += score.normalized_score_0_1 * w
            active_weight += w
            if score.flagged:
                reasons.append(score.explanation)

        composite_risk = (weighted_sum / active_weight) if active_weight > 0 else 0.0
        composite_risk = round(composite_risk, 3)

        # Categorize likelihood
        if composite_risk >= 0.60:
            likelihood = AuthenticityLikelihood.HIGH
            confidence = min(0.95, round(composite_risk + 0.10, 2))
        elif composite_risk >= 0.35:
            likelihood = AuthenticityLikelihood.MEDIUM
            confidence = round(composite_risk, 2)
        else:
            likelihood = AuthenticityLikelihood.LOW
            confidence = round(1.0 - composite_risk, 2)

        if not reasons:
            reasons.append("Answer exhibits natural spoken cadence, original phrasing, and organic formulation pauses.")

        return AuthenticityReport(
            likelihood=likelihood,
            confidence=confidence,
            composite_risk_score_0_1=composite_risk,
            reasons=reasons,
            signals=signals,
        )

    # -------------------------------------------------------------------------
    # Composite Assessment for Entire Viva Session
    # -------------------------------------------------------------------------
    def aggregate_session(
        self,
        turn_reports: List[AuthenticityReport],
    ) -> AuthenticityReport:
        """Aggregate turn-level reports into an overall session authenticity overview."""
        if not turn_reports:
            return AuthenticityReport(
                likelihood=AuthenticityLikelihood.UNKNOWN,
                confidence=0.0,
                composite_risk_score_0_1=0.0,
                reasons=["No turns completed yet."],
                signals={},
            )

        avg_risk = sum(r.composite_risk_score_0_1 for r in turn_reports) / len(turn_reports)
        avg_risk = round(avg_risk, 3)

        # Aggregate unique flagged reasons
        unique_reasons: List[str] = []
        for r in turn_reports:
            for reason in r.reasons:
                if reason not in unique_reasons and not reason.startswith("Answer exhibits natural"):
                    unique_reasons.append(reason)

        if avg_risk >= 0.55:
            likelihood = AuthenticityLikelihood.HIGH
            confidence = min(0.95, round(avg_risk + 0.15, 2))
        elif avg_risk >= 0.32:
            likelihood = AuthenticityLikelihood.MEDIUM
            confidence = round(avg_risk, 2)
        else:
            likelihood = AuthenticityLikelihood.LOW
            confidence = round(1.0 - avg_risk, 2)

        if not unique_reasons:
            unique_reasons.append("Consistent natural oral answers throughout the entire viva session.")

        # Aggregate signal scores
        merged_signals: Dict[str, SignalScore] = {}
        if turn_reports:
            for sig_key in turn_reports[0].signals:
                vals = [r.signals[sig_key].raw_value for r in turn_reports if sig_key in r.signals]
                norms = [r.signals[sig_key].normalized_score_0_1 for r in turn_reports if sig_key in r.signals]
                if vals:
                    merged_signals[sig_key] = SignalScore(
                        name=sig_key,
                        raw_value=round(sum(vals) / len(vals), 2),
                        normalized_score_0_1=round(sum(norms) / len(norms), 2),
                        threshold=turn_reports[0].signals[sig_key].threshold,
                        flagged=(sum(norms) / len(norms)) > 0.4,
                        explanation=f"Session-averaged metric across {len(vals)} turns.",
                    )

        return AuthenticityReport(
            likelihood=likelihood,
            confidence=confidence,
            composite_risk_score_0_1=avg_risk,
            reasons=unique_reasons,
            signals=merged_signals,
        )


_authenticity_analyzer: Optional[AuthenticityAnalyzer] = None


def get_authenticity_analyzer() -> AuthenticityAnalyzer:
    """Singleton factory for AuthenticityAnalyzer."""
    global _authenticity_analyzer
    if _authenticity_analyzer is None:
        _authenticity_analyzer = AuthenticityAnalyzer()
    return _authenticity_analyzer
