"""Grok (xAI) LLM Provider."""

from typing import Any, AsyncGenerator, Dict, Optional
import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider


class GrokProvider(BaseLLMProvider):
    """xAI Grok provider using OpenAI-compatible endpoints."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROK_API_KEY
        self.model = model or settings.GROK_MODEL
        self.base_url = "https://api.x.ai/v1"

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        if not self.api_key:
            raise ValueError("GROK_API_KEY is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "messages": messages}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"Grok API error {resp.status_code}: {resp.text}")
            return resp.json()["choices"][0]["message"]["content"].strip()

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        text = await self.generate_text(prompt, system)
        return self.clean_json_string(text)

    async def generate_stream(
        self, prompt: str, system: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        text = await self.generate_text(prompt, system)
        for chunk in text.split(" "):
            yield chunk + " "
