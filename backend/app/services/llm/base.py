"""Base LLM Provider abstract interface."""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.core.logging import logger

# Status codes worth retrying: rate limiting and transient upstream failures.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM providers."""

    name = "llm"
    max_retries = 3
    backoff_base_seconds = 0.5

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None, timeout: float = 60.0):
        # transport is injectable so tests can serve canned responses without a network.
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def _post_json(self, url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Any:
        """POST and return the decoded JSON body, retrying transient failures with exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with self._client() as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                error = RuntimeError(f"{self.name} API error {resp.status_code}: {resp.text[:300]}")
                if resp.status_code not in RETRYABLE_STATUS:
                    raise error
                last_error = error
            except httpx.TransportError as exc:  # includes timeouts
                last_error = RuntimeError(f"{self.name} unreachable: {exc.__class__.__name__}")
            if attempt < self.max_retries - 1:
                delay = self.backoff_base_seconds * (2**attempt)
                logger.warning(f"{self.name} request failed ({last_error}); retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

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


async def iter_sse_data(response: httpx.Response) -> AsyncGenerator[str, None]:
    """Yield the `data:` payloads of a server-sent-events stream, stopping at `[DONE]`."""
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        if data:
            yield data
