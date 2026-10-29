"""Gemini LLM Provider for production cloud execution."""

import json
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, iter_sse_data


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider via REST API."""

    name = "Gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        super().__init__(transport=transport, timeout=30.0)
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        # Header, not ?key= query param, so the key never appears in request/access logs.
        return {"x-goog-api-key": self.api_key}

    def _payload(self, prompt: str, system: Optional[str], json_mode: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        if json_mode:
            payload["generationConfig"] = {"responseMimeType": "application/json"}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    @staticmethod
    def _candidate_text(data: Dict[str, Any]) -> str:
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            return ""
        return "".join(str(p.get("text", "")) for p in parts)

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        headers = self._headers()
        data = await self._post_json(
            f"{self.base_url}/{self.model}:generateContent", self._payload(prompt, system), headers
        )
        text = self._candidate_text(data).strip()
        if not text:
            raise RuntimeError("Gemini returned no candidate text (possibly blocked by safety filters)")
        return text

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        headers = self._headers()
        data = await self._post_json(
            f"{self.base_url}/{self.model}:generateContent", self._payload(prompt, system, json_mode=True), headers
        )
        return self.clean_json_string(self._candidate_text(data))

    async def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        headers = self._headers()
        url = f"{self.base_url}/{self.model}:streamGenerateContent?alt=sse"
        async with self._client() as client:
            async with client.stream("POST", url, json=self._payload(prompt, system), headers=headers) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Gemini streaming error: {response.status_code}")
                async for data in iter_sse_data(response):
                    text = self._candidate_text(json.loads(data))
                    if text:
                        yield text
