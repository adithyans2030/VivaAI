"""LLM Gateway Package and Provider Factory."""

from typing import Optional

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.grok import GrokProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.ollama import OllamaProvider

_llm_instance: Optional[BaseLLMProvider] = None


def get_llm_provider(force_provider: Optional[str] = None) -> BaseLLMProvider:
    """Retrieve the configured LLM Provider singleton."""
    global _llm_instance

    provider_name = force_provider or settings.LLM_PROVIDER

    if provider_name == "ollama":
        # Check if user has llama3.1:latest or gemma2:2b
        model = settings.OLLAMA_MODEL
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=model)
    elif provider_name == "gemini":
        return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    elif provider_name == "grok":
        return GrokProvider(api_key=settings.GROK_API_KEY, model=settings.GROK_MODEL)
    else:
        if not settings.DEMO_MODE and settings.ENVIRONMENT != "testing":
            raise RuntimeError(
                "LLM_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True. "
                "Configure 'ollama', 'gemini', or 'grok', or set DEMO_MODE=True."
            )
        return MockLLMProvider()
