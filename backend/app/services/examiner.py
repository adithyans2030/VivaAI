"""AI Examiner service for question formulation and adaptive topic progression."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.core.logging import logger
from app.services.llm import get_llm_provider
from app.services.rag import get_rag_store

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class GeneratedQuestion(BaseModel):
    turn_number: int
    topic: str
    question_type: str
    question_text: str
    expected_key_points: List[str] = []
    source_references: List[Dict[str, Any]] = []
    prompt_version: str = "v1.0"


class ExaminerService:
    """Orchestrates adaptive viva voce questioning grounded in RAG subject context."""

    def __init__(
        self,
        prompt_version: str = "v1",
        llm_provider: Optional[Any] = None,
    ):
        self.prompt_version = prompt_version
        self.llm = llm_provider or get_llm_provider()
        self.question_prompt_template = self._load_prompt("question_generation.txt")
        self.probe_prompt_template = self._load_prompt("followup_probe.txt")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_version / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Versioned prompt template not found at '{prompt_path}'")
        return prompt_path.read_text(encoding="utf-8")

    def determine_next_question_type(
        self,
        turn_number: int,
        running_score: float,
        previous_types: List[str],
    ) -> str:
        """Adaptive question type selection based on turn index and performance."""
        if turn_number == 1:
            return "warmup"

        # Adaptive difficulty curve:
        # High performers (>7.5) receive deeper application, 'why', 'what_if', or probe questions
        # Low performers (<5.0) receive conceptual or clarifying questions
        if running_score >= 7.5:
            candidates = ["application", "compare_contrast", "why", "what_if", "probe"]
        elif running_score < 5.0:
            candidates = ["conceptual", "why"]
        else:
            candidates = ["conceptual", "application", "compare_contrast"]

        # Avoid immediate duplicate question type
        for c in candidates:
            if not previous_types or c != previous_types[-1]:
                return c
        return candidates[0]

    async def generate_question(
        self,
        subject_id: str,
        subject_name: str,
        turn_number: int,
        covered_topics: List[str],
        current_running_score: float = 7.0,
        previous_question_types: Optional[List[str]] = None,
        preferred_topic: Optional[str] = None,
        followup_context: Optional[Dict[str, Any]] = None,
    ) -> GeneratedQuestion:
        """Formulate the next exam question grounded in RAG material."""
        # Handle targeted follow-up probe if flagged
        if followup_context and turn_number > 1:
            orig_q = followup_context.get("question", "")
            ans = followup_context.get("answer", "")
            gap = followup_context.get("type", "Deepen conceptual understanding")
            probe_text = await self.generate_probe(
                subject_name=subject_name,
                original_question=orig_q,
                student_answer=ans,
                gap_description=gap,
            )
            return GeneratedQuestion(
                turn_number=turn_number,
                topic=preferred_topic or "Follow-up Probe",
                question_type="probe",
                question_text=probe_text,
                expected_key_points=["Authentic spontaneous reasoning", "Clear conceptual analogy"],
                source_references=[],
                prompt_version=f"{self.prompt_version}.0",
            )

        q_type = self.determine_next_question_type(turn_number, current_running_score, previous_question_types or [])

        # Handle warmup turn
        if q_type == "warmup":
            return GeneratedQuestion(
                turn_number=1,
                topic="Introduction & Baseline",
                question_type="warmup",
                question_text=(
                    f"Welcome to your oral viva examination in {subject_name}. "
                    "To begin, please introduce yourself and mention which topic you enjoyed studying the most."
                ),
                expected_key_points=["Candidate self-introduction", "Comfortable conversational response"],
                source_references=[],
                prompt_version=f"{self.prompt_version}.0",
            )

        # Retrieve grounded subject material via RAG
        rag_store = get_rag_store()
        query = preferred_topic or "core principles, architecture, algorithms, and key concepts"
        retrieved = await rag_store.retrieve(subject_id, query=query, top_k=3)

        context_text = retrieved.combined_context or (
            "Operating Systems principles: Processes, Concurrency, Deadlock Coffman conditions "
            "(Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait), Banker's Algorithm, "
            "Paging and Virtual Memory."
        )

        # Populate versioned prompt template
        filled_prompt = self.question_prompt_template
        filled_prompt = filled_prompt.replace("{{subject_name}}", subject_name)
        filled_prompt = filled_prompt.replace("{{retrieved_context}}", context_text)
        filled_prompt = filled_prompt.replace("{{previous_topics}}", ", ".join(covered_topics) or "None")
        filled_prompt = filled_prompt.replace("{{current_score}}", f"{current_running_score:.1f}")
        filled_prompt = filled_prompt.replace("{{question_type}}", q_type)
        filled_prompt = filled_prompt.replace("{{topic}}", preferred_topic or "Core Subject Concept")

        # Call LLM provider
        try:
            result_json = await self.llm.generate_json(filled_prompt)
            q_text = result_json.get("question_text", "Explain the core concepts of this topic.")
            topic = result_json.get("topic", preferred_topic or "Core Subject Concept")
            key_points = result_json.get("expected_key_points", [])
        except Exception as e:
            logger.error(f"LLM question generation failed: {e}. Using deterministic fallback.")
            q_text = "What are the four necessary Coffman conditions required for a deadlock to occur?"
            topic = "Deadlocks"
            key_points = ["Mutual Exclusion", "Hold and Wait", "No Preemption", "Circular Wait"]

        # Serialize source references
        sources_payload = [s.model_dump() for s in retrieved.sources]

        return GeneratedQuestion(
            turn_number=turn_number,
            topic=topic,
            question_type=q_type,
            question_text=q_text,
            expected_key_points=key_points,
            source_references=sources_payload,
            prompt_version=f"{self.prompt_version}.0",
        )

    async def generate_probe(
        self,
        subject_name: str,
        original_question: str,
        student_answer: str,
        gap_description: str,
    ) -> str:
        """Formulate a probing follow-up question testing real understanding vs rote memorization."""
        prompt = self.probe_prompt_template
        prompt = prompt.replace("{{subject_name}}", subject_name)
        prompt = prompt.replace("{{original_question}}", original_question)
        prompt = prompt.replace("{{student_answer}}", student_answer)
        prompt = prompt.replace("{{gap_description}}", gap_description)

        try:
            res = await self.llm.generate_json(prompt)
            return res.get(
                "question_text",
                "Can you explain that concept in your own words with an everyday analogy?",
            )
        except Exception as e:
            logger.warning(f"Probe generation fallback: {e}")
            return "Could you give a concrete real-world example of that from outside the course slides?"


_examiner_instance: Optional[ExaminerService] = None


def get_examiner_service() -> ExaminerService:
    global _examiner_instance
    if _examiner_instance is None:
        _examiner_instance = ExaminerService()
    return _examiner_instance
