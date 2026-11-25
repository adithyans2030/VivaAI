"""AI Grader service for multi-dimensional rubric scoring, repair prompting, and prompt-injection defense."""

import re
from pathlib import Path
from typing import Any, List, Optional

from app.core.logging import logger
from app.schemas.turn import GraderResult, RubricBreakdown
from app.services.llm import get_llm_provider

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class GraderService:
    """Evaluates candidate spoken responses against retrieved course ground-truth."""

    def __init__(
        self,
        prompt_version: str = "v1",
        llm_provider: Optional[Any] = None,
    ):
        self.prompt_version = prompt_version
        self.llm = llm_provider or get_llm_provider()
        self.grading_prompt_template = self._load_prompt("answer_grading.txt")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_version / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Versioned prompt template not found at '{prompt_path}'")
        return prompt_path.read_text(encoding="utf-8")

    def detect_adversarial_injection(self, text: str) -> bool:
        """Heuristic check for common prompt injection patterns in untrusted student speech."""
        patterns = [
            r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
            r"give\s+me\s+(a\s+)?10(\.0)?(\s+out\s+of\s+10)?",
            r"system\s+prompt",
            r"you\s+are\s+now\s+in\s+developer\s+mode",
            r"disregard\s+the\s+rubric",
            r"act\s+as\s+a\s+different",
        ]
        text_lower = text.lower()
        for p in patterns:
            if re.search(p, text_lower):
                return True
        return False

    async def grade_answer(
        self,
        subject_name: str,
        question_text: str,
        student_answer: str,
        expected_key_points: List[str],
        retrieved_context: str = "",
    ) -> GraderResult:
        """Grade student answer against course ground-truth with repair prompting on JSON failure."""
        answer_clean = student_answer.strip()

        # Handle empty answer
        if not answer_clean:
            return GraderResult(
                score_0_10=0.0,
                grading_status="completed",
                rubric=RubricBreakdown(
                    correctness=0.0,
                    completeness=0.0,
                    clarity=0.0,
                    depth=0.0,
                    missing_points=expected_key_points or ["Response was silent or absent"],
                    incorrect_claims=[],
                ),
                feedback="No audible response was detected for this question.",
                followup_needed=True,
                followup_type="clarification",
            )

        # Handle adversarial prompt injection (Flag for teacher review, do not automatically score 0)
        security_flag = None
        if self.detect_adversarial_injection(answer_clean):
            # Never log the answer itself: it is student data. The caller logs the turn ID.
            logger.warning("Adversarial prompt injection pattern detected in a student answer.")
            security_flag = "prompt_injection_attempt"

        # Handle "I don't know" or brief admissions of unfamiliarity
        idk_patterns = [r"^i\s+(do\s+not|don't)\s+know", r"^no\s+idea", r"^not\s+sure"]
        if any(re.search(p, answer_clean.lower()) for p in idk_patterns):
            return GraderResult(
                score_0_10=1.5,
                grading_status="completed",
                security_flag=security_flag,
                rubric=RubricBreakdown(
                    correctness=1.0,
                    completeness=1.0,
                    clarity=3.0,
                    depth=1.0,
                    missing_points=expected_key_points,
                    incorrect_claims=[],
                ),
                feedback="Acknowledged unfamiliarity. Let's move to a related foundational topic.",
                followup_needed=False,
                followup_type="none",
            )

        # Build prompt from versioned template with full context injection
        prompt = self.grading_prompt_template
        prompt = prompt.replace("{{subject_name}}", subject_name)
        prompt = prompt.replace("{{retrieved_context}}", retrieved_context or "General curriculum standard")
        prompt = prompt.replace("{{question_text}}", question_text)
        prompt = prompt.replace("{{expected_key_points}}", "\n- ".join(expected_key_points) or "Key principles")
        prompt = prompt.replace("{{student_answer}}", answer_clean)

        res_json = None
        try:
            res_json = await self.llm.generate_json(prompt)
        except Exception as first_err:
            logger.warning(f"Initial LLM grading JSON parsing failed: {first_err}. Attempting repair prompt...")
            # Repair prompt fallback
            repair_prompt = (
                f"The previous response to grading the student answer was not valid JSON. "
                f"Please fix and return ONLY a valid JSON object matching the required schema with keys "
                f"'score_0_10', 'rubric', 'feedback', 'followup_needed', 'followup_type'.\n"
                f"Subject: {subject_name}\nQuestion: {question_text}\nAnswer: {answer_clean}"
            )
            try:
                res_json = await self.llm.generate_json(repair_prompt)
            except Exception as repair_err:
                logger.error(f"LLM grading repair prompt also failed: {repair_err}. Marking grading as failed.")
                # Mark turn as failed without numerical score; alert teacher (never default to 7.5)
                return GraderResult(
                    score_0_10=None,
                    grading_status="failed",
                    security_flag=security_flag,
                    rubric=RubricBreakdown(
                        correctness=0.0,
                        completeness=0.0,
                        clarity=0.0,
                        depth=0.0,
                        missing_points=[],
                        incorrect_claims=[],
                    ),
                    feedback="Grading unavailable — teacher review required.",
                    followup_needed=False,
                    followup_type="none",
                )

        # Validate rubric structure
        rubric_data = res_json.get("rubric", {})
        correctness = float(rubric_data.get("correctness", 7.0))
        completeness = float(rubric_data.get("completeness", 7.0))
        clarity = float(rubric_data.get("clarity", 7.0))
        depth = float(rubric_data.get("depth", 7.0))

        # Recompute score_0_10 strictly according to weighted rubric formula (WS-6 Rubric Consistency)
        # Formula: (correctness * 0.40) + (completeness * 0.25) + (clarity * 0.15) + (depth * 0.20)
        computed_score = (correctness * 0.40) + (completeness * 0.25) + (clarity * 0.15) + (depth * 0.20)
        score_0_10 = round(max(0.0, min(10.0, computed_score)), 1)

        rubric = RubricBreakdown(
            correctness=correctness,
            completeness=completeness,
            clarity=clarity,
            depth=depth,
            missing_points=rubric_data.get("missing_points", []),
            incorrect_claims=rubric_data.get("incorrect_claims", []),
        )

        feedback_text = res_json.get("feedback", "Good effort answering the question.")
        if security_flag:
            feedback_text = f"{feedback_text} [Notice: Input pattern flagged for teacher review]"

        return GraderResult(
            score_0_10=score_0_10,
            grading_status="completed",
            security_flag=security_flag,
            rubric=rubric,
            feedback=feedback_text,
            followup_needed=bool(res_json.get("followup_needed", False)),
            followup_type=res_json.get("followup_type", "none"),
        )


_grader_instance: Optional[GraderService] = None


def get_grader_service() -> GraderService:
    global _grader_instance
    if _grader_instance is None:
        _grader_instance = GraderService()
    return _grader_instance
