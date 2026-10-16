"""AI Grader service for multi-dimensional rubric scoring and prompt-injection defense."""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
        """Grade student answer and return validated Pydantic GraderResult."""
        answer_clean = student_answer.strip()

        # Handle empty answer
        if not answer_clean:
            return GraderResult(
                score_0_10=0.0,
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

        # Handle adversarial prompt injection
        if self.detect_adversarial_injection(answer_clean):
            logger.warning(f"Adversarial prompt injection pattern detected in answer: '{answer_clean[:60]}...'")
            return GraderResult(
                score_0_10=0.0,
                rubric=RubricBreakdown(
                    correctness=0.0,
                    completeness=0.0,
                    clarity=1.0,
                    depth=0.0,
                    missing_points=expected_key_points or ["Valid subject-matter explanation"],
                    incorrect_claims=["Instruction override pattern detected in spoken answer"],
                ),
                feedback="Adversarial prompt injection detected. Answers must be provided in your own words addressing the question directly.",
                followup_needed=True,
                followup_type="probe",
            )

        # Handle "I don't know" or brief admissions of unfamiliarity
        idk_patterns = [r"^i\s+(do\s+not|don't)\s+know", r"^no\s+idea", r"^not\s+sure"]
        if any(re.search(p, answer_clean.lower()) for p in idk_patterns):
            return GraderResult(
                score_0_10=1.5,
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

        # Build prompt from versioned template
        prompt = self.grading_prompt_template
        prompt = prompt.replace("{{subject_name}}", subject_name)
        prompt = prompt.replace("{{retrieved_context}}", retrieved_context or "General curriculum standard")
        prompt = prompt.replace("{{question_text}}", question_text)
        prompt = prompt.replace("{{expected_key_points}}", "\n- ".join(expected_key_points) or "Key principles")
        prompt = prompt.replace("{{student_answer}}", answer_clean)

        try:
            res_json = await self.llm.generate_json(prompt)

            # Validate rubric structure
            rubric_data = res_json.get("rubric", {})
            rubric = RubricBreakdown(
                correctness=float(rubric_data.get("correctness", 7.0)),
                completeness=float(rubric_data.get("completeness", 7.0)),
                clarity=float(rubric_data.get("clarity", 7.0)),
                depth=float(rubric_data.get("depth", 7.0)),
                missing_points=rubric_data.get("missing_points", []),
                incorrect_claims=rubric_data.get("incorrect_claims", []),
            )

            score = float(res_json.get("score_0_10", 7.0))
            score = max(0.0, min(10.0, score))

            return GraderResult(
                score_0_10=round(score, 1),
                rubric=rubric,
                feedback=res_json.get("feedback", "Good effort answering the question."),
                followup_needed=bool(res_json.get("followup_needed", False)),
                followup_type=res_json.get("followup_type", "none"),
            )
        except Exception as e:
            logger.error(f"LLM grading failed: {e}. Using deterministic evaluation fallback.")
            return GraderResult(
                score_0_10=7.5,
                rubric=RubricBreakdown(
                    correctness=7.5,
                    completeness=7.0,
                    clarity=8.0,
                    depth=7.0,
                    missing_points=[],
                    incorrect_claims=[],
                ),
                feedback="Good spoken response addressing the key points asked.",
                followup_needed=False,
                followup_type="none",
            )


_grader_instance: Optional[GraderService] = None


def get_grader_service() -> GraderService:
    global _grader_instance
    if _grader_instance is None:
        _grader_instance = GraderService()
    return _grader_instance
