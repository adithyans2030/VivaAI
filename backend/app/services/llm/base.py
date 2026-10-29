"""Base LLM Provider abstract interface."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate a single text response."""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON validated against a schema."""
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Generate streaming token chunks."""
        pass

    def clean_json_string(self, raw_output: str) -> Dict[str, Any]:
        """Helper to extract and clean valid JSON from model responses."""
        raw_output = raw_output.strip()
        # Remove markdown code fences if present
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        elif raw_output.startswith("```"):
            raw_output = raw_output[3:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
        raw_output = raw_output.strip()

        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            # Fallback regex search for outer brackets
            match = re.search(r"(\{.*\})", raw_output, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse valid JSON from LLM output: {raw_output[:200]}...")
