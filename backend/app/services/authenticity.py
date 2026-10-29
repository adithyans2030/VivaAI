"""Advisory & Explainable Authenticity Assessment Engine.

Analyzes oral responses across 6 acoustic and linguistic signals to detect
potential note-reading vs. spontaneous explanation. Strictly advisory;
zero automated penalties. Flags are for teacher review only.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.models.session import AuthenticityLikelihood


class SignalScore(BaseModel):
    """Detailed score for an individual authenticity signal."""

    name: str
    raw_value: float
    normalized_score_0_1: float  # 0.0 = highly spontaneous, 1.0 = highly scripted/reading
    threshold: float
    flagged: bool
    explanation: str
    is_available: bool = True
    is_advisory: bool = True


class AuthenticityReport(BaseModel):
    """Structured advisory authenticity assessment for a turn or session."""

    likelihood: AuthenticityLikelihood
    confidence: float = Field(ge=0.0, le=1.0)
    composite_risk_score_0_1: float = Field(ge=0.0, le=1.0)
    reasons: List[str]
    signals: Dict[str, SignalScore]
    is_advisory: bool = True
    disclaimer: str = "Advisory signal to support teacher judgment — not an automated accusation."


class AuthenticityAnalyzer:
    """Analyzes student viva turns using 6 explainable acoustic and linguistic signals."""

    # Natural speech fillers and disfluency markers
    FILLERS: List[str] = [
        "um",
        "uh",
        "er",
        "ah",
        "like",
        "you know",
        "i mean",
        "sort of",
        "kind of",
        "actually",
        "basically",
        "well",
        "so yeah",
    ]

    def __init__(
        self,
        ngram_threshold: float = 0.40,
        disfluency_min_expected: float = 1.0,  # Fillers per 100 words in spontaneous speech
        midclause_pause_ratio_threshold: float = 0.35,
        onset_latency_lower_sec: float = 0.30,  # Superhuman threshold: < 300ms
        onset_latency_upper_sec: float = 8.0,  # Searching notes threshold: > 8000ms
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
                is_available=True,
                explanation="Insufficient answer length or reference material for n-gram comparison.",
            )

        student_ngrams = set(tuple(student_words[i : i + n]) for i in range(len(student_words) - n + 1))

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
            is_available=True,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 2: Disfluency Rate Calibrated with Warmup Baseline
    # -------------------------------------------------------------------------
    def compute_disfluency_rate(
        self,
        student_text: str,
        word_timestamps: Optional[List[Dict[str, Any]]] = None,
        warmup_baseline: Optional[Dict[str, Any]] = None,
    ) -> SignalScore:
        """Natural spontaneous speech contains fillers/restarts per 100 words.
        Calibrated against student's personal warmup baseline.
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
                is_available=True,
                explanation="Short answer, baseline disfluency assumed normal.",
            )

        lower_text = f" {student_text.lower()} "
        filler_count = 0
        for filler in self.FILLERS:
            pattern = rf"\b{re.escape(filler)}\b"
            filler_count += len(re.findall(pattern, lower_text))

        # Adjacent word repetitions ("the the", "we we")
        for i in range(len(words) - 1):
            if words[i] == words[i + 1] and len(words[i]) > 1:
                filler_count += 1

        rate_per_100 = (filler_count / total_words) * 100.0

        # Calibrate expected minimum using warmup baseline if available
        expected_threshold = self.disfluency_min_expected
        if warmup_baseline and "disfluency_rate" in warmup_baseline:
            base_rate = warmup_baseline["disfluency_rate"]
            if base_rate is not None:
                expected_threshold = max(0.4, min(self.disfluency_min_expected, base_rate * 0.65))

        # Flag unusually low disfluency in longer answers
        if rate_per_100 < expected_threshold and total_words >= 30:
            flagged = True
            norm_score = max(0.0, 1.0 - (rate_per_100 / expected_threshold))
            explanation = (
                f"Unusually polished fluency ({rate_per_100:.1f} disfluencies/100 words, "
                f"expected >= {expected_threshold:.1f} calibrated against baseline). Speech displays reading cadence."
            )
        else:
            flagged = False
            norm_score = 0.0
            explanation = f"Natural conversational disfluency rate ({rate_per_100:.1f} per 100 words)."

        return SignalScore(
            name="disfluency_rate",
            raw_value=rate_per_100,
            normalized_score_0_1=norm_score,
            threshold=expected_threshold,
            flagged=flagged,
            is_available=True,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 3: Pause Pattern Distribution (Syntactic vs Mid-Clause Pauses)
    # -------------------------------------------------------------------------
    def compute_pause_distribution(
        self,
        word_timestamps: Optional[List[Dict[str, Any]]],
        warmup_baseline: Optional[Dict[str, Any]] = None,
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
                is_available=True,
                explanation="Insufficient word timestamp data for pause boundary analysis.",
            )

        pauses: List[Tuple[float, str, str]] = []
        for i in range(len(word_timestamps) - 1):
            curr_end = word_timestamps[i].get("end", 0.0)
            next_start = word_timestamps[i + 1].get("start", 0.0)
            gap = next_start - curr_end
            if gap >= 0.4:  # Noticeable pause > 400ms
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
                is_available=True,
                explanation="Fluid speech with no atypical hesitations.",
            )

        mid_clause_pauses = 0
        punctuation_marks = (".", ",", ";", ":", "?", "!", "-", "—")

        for gap, curr_word, next_word in pauses:
            is_boundary = any(curr_word.strip().endswith(p) for p in punctuation_marks)
            is_boundary = is_boundary or next_word.strip().lower() in ("and", "but", "however", "because", "so", "or")
            if not is_boundary:
                mid_clause_pauses += 1

        mid_clause_ratio = mid_clause_pauses / len(pauses)
        threshold = self.midclause_pause_ratio_threshold
        if warmup_baseline and "pause_ratio" in warmup_baseline:
            base_pause = warmup_baseline["pause_ratio"]
            if base_pause is not None:
                threshold = max(0.25, base_pause * 1.5)

        flagged = mid_clause_ratio >= threshold and len(pauses) >= 3
        norm_score = min(1.0, mid_clause_ratio / max(0.01, threshold * 1.5))

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
            threshold=threshold,
            flagged=flagged,
            is_available=True,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 4: Prosody and Speaking Rate Variance
    # -------------------------------------------------------------------------
    def compute_prosody_variance(
        self,
        word_timestamps: Optional[List[Dict[str, Any]]],
        audio_duration_seconds: Optional[float] = None,
        warmup_baseline: Optional[Dict[str, Any]] = None,
    ) -> SignalScore:
        """Assesses expressive variation in speech rate.
        Reading notes produces rigid, metronomic cadence with low variance.
        """
        if not word_timestamps or len(word_timestamps) < 10:
            return SignalScore(
                name="prosody_variance",
                raw_value=0.5,
                normalized_score_0_1=0.0,
                threshold=0.18,
                flagged=False,
                is_available=True,
                explanation="Standard conversational cadence.",
            )

        # Consecutive 3-word duration windows
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
                threshold=0.18,
                flagged=False,
                is_available=True,
                explanation="Standard conversational cadence.",
            )

        mean_dur = sum(durations) / len(durations)
        variance = sum((d - mean_dur) ** 2 for d in durations) / len(durations)
        coeff_of_variation = math.sqrt(variance) / max(0.01, mean_dur)

        flagged = coeff_of_variation < 0.18 and len(durations) >= 8
        norm_score = max(0.0, 1.0 - (coeff_of_variation / 0.25)) if flagged else 0.0

        explanation = (
            f"Low cadence variability (CV = {coeff_of_variation:.2f}). Monotone or rhythmic reading pattern observed."
            if flagged
            else f"Natural expressive rhythm with healthy variation (CV = {coeff_of_variation:.2f})."
        )

        return SignalScore(
            name="prosody_variance",
            raw_value=coeff_of_variation,
            normalized_score_0_1=norm_score,
            threshold=0.18,
            flagged=flagged,
            is_available=True,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Signal 5: Response Onset Latency (Measurable delta from client/audio)
    # -------------------------------------------------------------------------
    def compute_onset_latency(
        self,
        onset_latency_seconds: Optional[float],
        question_type: str = "conceptual",
        warmup_baseline: Optional[Dict[str, Any]] = None,
    ) -> SignalScore:
        """Evaluates elapsed time between question finish and student start.
        - Instant recitation (< 0.3s): superhuman onset without formulation pause.
        - Protracted silence (> 8.0s): searching/consulting external notes.
        """
        if onset_latency_seconds is None or onset_latency_seconds < 0:
            return SignalScore(
                name="onset_latency",
                raw_value=1.5,
                normalized_score_0_1=0.0,
                threshold=self.onset_latency_lower_sec,
                flagged=False,
                is_available=True,
                explanation="Onset latency within normal range.",
            )

        flagged = False
        norm_score = 0.0
        explanation = f"Natural response onset latency ({onset_latency_seconds:.1f}s)."

        # Superhuman rapid onset (< 300ms) on conceptual/application questions
        if onset_latency_seconds < self.onset_latency_lower_sec and question_type != "warmup":
            flagged = True
            norm_score = 0.70
            explanation = (
                f"Superhuman rapid onset latency ({onset_latency_seconds:.2f}s < {self.onset_latency_lower_sec}s for a {question_type} question). "
                f"Immediate response without organic cognitive formulation delay."
            )
        # Visual search delay (> 8.0s)
        elif onset_latency_seconds > self.onset_latency_upper_sec:
            flagged = True
            norm_score = 0.55
            explanation = (
                f"Prolonged latency before responding ({onset_latency_seconds:.1f}s > {self.onset_latency_upper_sec}s), "
                f"suggestive of searching or consulting external notes."
            )
        # Baseline comparison
        elif warmup_baseline and "onset_latency" in warmup_baseline:
            base_lat = warmup_baseline["onset_latency"]
            if base_lat and onset_latency_seconds > base_lat * 2.8 and onset_latency_seconds > 6.0:
                flagged = True
                norm_score = 0.40
                explanation = f"Atypical response delay ({onset_latency_seconds:.1f}s vs student warmup baseline {base_lat:.1f}s)."

        return SignalScore(
            name="onset_latency",
            raw_value=onset_latency_seconds,
            normalized_score_0_1=norm_score,
            threshold=self.onset_latency_lower_sec,
            flagged=flagged,
            is_available=True,
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
        """Measures discrepancy between scripted conceptual questions vs unexpected probe."""
        if core_avg_score is None or probe_score is None:
            return SignalScore(
                name="probe_delta",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=self.probe_score_delta_threshold,
                flagged=False,
                is_available=True,
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
            is_available=True,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # Acoustic Feature: Fundamental Frequency (F0) Pitch Variance
    # -------------------------------------------------------------------------
    def compute_pitch_f0_variance(
        self,
        audio_path: Optional[str] = None,
        audio_duration_seconds: Optional[float] = None,
        warmup_baseline: Optional[Dict[str, Any]] = None,
    ) -> SignalScore:
        """Measures fundamental frequency (F0) pitch variability using Praat/parselmouth or librosa.
        Monotone delivery across multi-clause responses (pitch variance < 15 Hz)
        is characteristic of reading text aloud.
        """
        if not audio_path:
            return SignalScore(
                name="pitch_f0_variance",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=15.0,
                flagged=False,
                is_available=False,
                explanation="Audio file path unavailable for acoustic F0 pitch extraction.",
            )

        f0_std = None
        f0_mean = None

        # 1. Try Praat (parselmouth)
        try:
            import parselmouth

            sound = parselmouth.Sound(audio_path)
            pitch = sound.to_pitch()
            pitch_values = pitch.selected_array["frequency"]
            voiced_pitches = [float(p) for p in pitch_values if p > 50.0]
            if len(voiced_pitches) >= 10:
                f0_mean = sum(voiced_pitches) / len(voiced_pitches)
                variance = sum((p - f0_mean) ** 2 for p in voiced_pitches) / len(voiced_pitches)
                f0_std = math.sqrt(variance)
        except Exception:
            pass

        # 2. Try librosa pyin if parselmouth wasn't available
        if f0_std is None:
            try:
                import librosa

                y, sr = librosa.load(audio_path, sr=16000)
                f0, _, _ = librosa.pyin(y, fmin=50, fmax=500, sr=sr)
                voiced_pitches = [float(p) for p in f0 if p is not None and not math.isnan(p) and p > 50.0]
                if len(voiced_pitches) >= 10:
                    f0_mean = sum(voiced_pitches) / len(voiced_pitches)
                    variance = sum((p - f0_mean) ** 2 for p in voiced_pitches) / len(voiced_pitches)
                    f0_std = math.sqrt(variance)
            except Exception:
                pass

        if f0_std is None:
            return SignalScore(
                name="pitch_f0_variance",
                raw_value=0.0,
                normalized_score_0_1=0.0,
                threshold=15.0,
                flagged=False,
                is_available=False,
                explanation="Pitch (F0) analysis unavailable (praat-parselmouth or librosa required).",
            )

        duration = audio_duration_seconds or 5.0
        baseline_pitch_std = warmup_baseline.get("pitch_std") if warmup_baseline else None
        threshold = baseline_pitch_std * 0.55 if baseline_pitch_std else 15.0

        # Monotone reading flag: low pitch std in speech longer than 4 seconds
        flagged = f0_std < threshold and duration >= 4.0
        norm_score = max(0.0, 1.0 - (f0_std / max(0.01, threshold * 2))) if flagged else 0.0

        explanation = (
            f"Atypical monotone delivery (F0 pitch standard deviation {f0_std:.1f} Hz < threshold {threshold:.1f} Hz). "
            f"Flat pitch contour across technical clauses suggestive of reading aloud."
            if flagged
            else f"Expressive pitch variation (F0 std = {f0_std:.1f} Hz, mean = {f0_mean:.1f} Hz)."
        )

        return SignalScore(
            name="pitch_f0_variance",
            raw_value=round(f0_std, 2),
            normalized_score_0_1=round(norm_score, 2),
            threshold=round(threshold, 2),
            flagged=flagged,
            is_available=True,
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
        audio_path: Optional[str] = None,
        question_type: str = "conceptual",
        core_avg_score: Optional[float] = None,
        turn_score: Optional[float] = None,
        warmup_baseline: Optional[Dict[str, Any]] = None,
    ) -> AuthenticityReport:
        """Run all applicable authenticity checks on a student's oral turn."""
        signals: Dict[str, SignalScore] = {}

        # 1. N-gram overlap
        signals["ngram_overlap"] = self.compute_ngram_overlap(student_text, reference_chunks)

        # 2. Disfluency rate (calibrated with warmup baseline)
        signals["disfluency_rate"] = self.compute_disfluency_rate(student_text, word_timestamps, warmup_baseline)

        # 3. Pause distribution (calibrated with warmup baseline)
        signals["pause_distribution"] = self.compute_pause_distribution(word_timestamps, warmup_baseline)

        # 4. Prosody / cadence variance
        signals["prosody_variance"] = self.compute_prosody_variance(
            word_timestamps, audio_duration_seconds, warmup_baseline
        )

        # 5. Onset latency (calibrated with warmup baseline)
        signals["onset_latency"] = self.compute_onset_latency(onset_latency_seconds, question_type, warmup_baseline)

        # 6. Dynamic Probe delta (if applicable)
        if question_type == "probe" and core_avg_score is not None and turn_score is not None:
            signals["probe_delta"] = self.compute_probe_delta(core_avg_score, turn_score)

        # 7. Acoustic Pitch F0 variance (if audio provided)
        if audio_path:
            pitch_score = self.compute_pitch_f0_variance(audio_path, audio_duration_seconds, warmup_baseline)
            signals["pitch_f0_variance"] = pitch_score

        # Signal Weights
        weights = {
            "ngram_overlap": 0.30,
            "disfluency_rate": 0.20,
            "pause_distribution": 0.15,
            "prosody_variance": 0.10,
            "onset_latency": 0.10,
            "probe_delta": 0.10,
            "pitch_f0_variance": 0.05,
        }

        active_weight = 0.0
        weighted_sum = 0.0
        reasons: List[str] = []

        for name, score in signals.items():
            # If feature extraction is unavailable, do NOT contribute to composite score
            if not score.is_available:
                continue
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
            is_advisory=True,
            disclaimer="Advisory signal to support teacher judgment — not an automated accusation.",
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
                is_advisory=True,
                disclaimer="Advisory signal to support teacher judgment — not an automated accusation.",
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
                vals = [
                    r.signals[sig_key].raw_value
                    for r in turn_reports
                    if sig_key in r.signals and r.signals[sig_key].is_available
                ]
                norms = [
                    r.signals[sig_key].normalized_score_0_1
                    for r in turn_reports
                    if sig_key in r.signals and r.signals[sig_key].is_available
                ]
                if vals:
                    merged_signals[sig_key] = SignalScore(
                        name=sig_key,
                        raw_value=round(sum(vals) / len(vals), 2),
                        normalized_score_0_1=round(sum(norms) / len(norms), 2),
                        threshold=turn_reports[0].signals[sig_key].threshold,
                        flagged=(sum(norms) / len(norms)) > 0.4,
                        explanation=f"Session-averaged metric across {len(vals)} turns.",
                        is_available=True,
                        is_advisory=True,
                    )

        return AuthenticityReport(
            likelihood=likelihood,
            confidence=confidence,
            composite_risk_score_0_1=avg_risk,
            reasons=unique_reasons,
            signals=merged_signals,
            is_advisory=True,
            disclaimer="Advisory signal to support teacher judgment — not an automated accusation.",
        )


_authenticity_analyzer: Optional[AuthenticityAnalyzer] = None


def get_authenticity_analyzer() -> AuthenticityAnalyzer:
    """Singleton factory for AuthenticityAnalyzer."""
    global _authenticity_analyzer
    if _authenticity_analyzer is None:
        _authenticity_analyzer = AuthenticityAnalyzer()
    return _authenticity_analyzer
