"""Ollama LLM Provider for local GPU/CPU execution."""

import json
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Local LLM provider using Ollama's REST API."""

    name = "Ollama"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        super().__init__(transport=transport, timeout=60.0)
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    def _payload(self, prompt: str, system: Optional[str], **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False, **extra}
        if system:
            payload["system"] = system
        return payload

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        data = await self._post_json(f"{self.base_url}/api/generate", self._payload(prompt, system))
        return str(data.get("response", "")).strip()

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        data = await self._post_json(f"{self.base_url}/api/generate", self._payload(prompt, system, format="json"))
        return self.clean_json_string(str(data.get("response", "")))

    async def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        payload = self._payload(prompt, system, stream=True)
        async with self._client() as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama streaming error: {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk_json = json.loads(line)
                    if chunk_json.get("response"):
                        yield chunk_json["response"]
                    if chunk_json.get("done", False):
                        break
