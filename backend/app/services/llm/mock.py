"""Mock LLM Provider for unit testing and offline CI execution."""

from typing import Any, AsyncGenerator, Dict, Optional

from app.services.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM provider."""

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        return "This is a deterministic mock LLM text response."

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        # Branch based on prompt keywords to return appropriate structured schema
        if "question_type" in prompt.lower() or "formulate one clear" in prompt.lower():
            return {
                "topic": "Deadlocks",
                "question_type": "conceptual",
                "question_text": "What are Coffman's four necessary conditions that must hold simultaneously for a deadlock to occur?",
                "expected_key_points": [
                    "Mutual Exclusion",
                    "Hold and Wait",
                    "No Preemption",
                    "Circular Wait",
                ],
            }
        elif "untrusted candidate spoken answer" in prompt.lower() or "score_0_10" in prompt.lower():
            # Grader response
            # Check for prompt injection inside the student answer section
            student_section = ""
            if '"""' in prompt:
                parts = prompt.split('"""')
                if len(parts) >= 2:
                    student_section = parts[1].lower()

            if "ignore previous instructions" in student_section:
                return {
                    "score_0_10": 0.0,
                    "rubric": {
                        "correctness": 0.0,
                        "completeness": 0.0,
                        "clarity": 1.0,
                        "depth": 0.0,
                        "missing_points": ["Valid factual answer"],
                        "incorrect_claims": ["Attempted instruction injection"],
                    },
                    "feedback": "Prompt injection attempt detected. No credit awarded for adversarial instructions.",
                    "followup_needed": True,
                    "followup_type": "probe",
                }

            return {
                "score_0_10": 8.5,
                "rubric": {
                    "correctness": 9.0,
                    "completeness": 8.0,
                    "clarity": 9.0,
                    "depth": 8.0,
                    "missing_points": ["Concrete practical example in modern kernels"],
                    "incorrect_claims": [],
                },
                "feedback": "Strong foundational explanation demonstrating clear understanding of synchronization concepts.",
                "followup_needed": False,
                "followup_type": "none",
            }
        elif "probe" in prompt.lower() or "in your own everyday words" in prompt.lower():
            return {
                "probe_type": "conceptual_depth",
                "question_text": "In your own everyday words, why is the Banker's algorithm considered impractical in high-performance operating systems?",
                "expected_understanding": "Processes cannot declare their maximum resource claims in advance.",
            }

        return {"result": "ok", "mock": True}

    async def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        tokens = ["What ", "are ", "the ", "four ", "conditions ", "for ", "deadlock?"]
        for token in tokens:
            yield token
