"""Ollama LLM Provider for local GPU/CPU execution."""

import json
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Local LLM provider using Ollama's REST API."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        # If user has llama3.1:latest or gemma2:2b installed, default gracefully
        self.model = model or settings.OLLAMA_MODEL

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data.get("response", "").strip()

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
            data = resp.json()
            raw_text = data.get("response", "")
            return self.clean_json_string(raw_text)

    async def generate_stream(self, prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama streaming error: {response.status_code}")
                async for line in response.aiter_lines():
                    if line.strip():
                        chunk_json = json.loads(line)
                        yield chunk_json.get("response", "")
                        if chunk_json.get("done", False):
                            break
