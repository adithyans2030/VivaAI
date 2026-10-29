"""Grok (xAI) LLM Provider."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, iter_sse_data


class GrokProvider(BaseLLMProvider):
    """xAI Grok provider using OpenAI-compatible endpoints."""

    name = "Grok"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        super().__init__(transport=transport, timeout=30.0)
        self.api_key = api_key or settings.GROK_API_KEY
        self.model = model or settings.GROK_MODEL
        self.base_url = "https://api.x.ai/v1"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("GROK_API_KEY is not configured")
        return {"Authorization": f"Bearer {self.api_key}"}

    def _payload(self, prompt: str, system: Optional[str], **extra: Any) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {"model": self.model, "messages": messages, **extra}

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        headers = self._headers()
        data = await self._post_json(f"{self.base_url}/chat/completions", self._payload(prompt, system), headers)
        return str(data["choices"][0]["message"]["content"]).strip()

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        headers = self._headers()
        payload = self._payload(prompt, system, response_format={"type": "json_object"})
        data = await self._post_json(f"{self.base_url}/chat/completions", payload, headers)
        return self.clean_json_string(str(data["choices"][0]["message"]["content"]))

    async def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        headers = self._headers()
        payload = self._payload(prompt, system, stream=True)
        async with self._client() as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Grok streaming error: {response.status_code}")
                async for data in iter_sse_data(response):
                    delta = json.loads(data)["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
