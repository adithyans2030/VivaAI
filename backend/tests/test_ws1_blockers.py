"""Tests verifying WS-1 fixes: secret validation, mock provider guardrails, and readiness probe."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_placeholder_secret_key(monkeypatch):
    """Verify that in production, default or placeholder SECRET_KEY raises a critical validation error."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-vivaiq-change-in-production-only")
    monkeypatch.setenv("STT_PROVIDER", "whisper")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "Production environment cannot use default or placeholder SECRET_KEY" in str(exc_info.value)


def test_mock_providers_rejected_without_testing_or_demo_mode(monkeypatch):
    """Verify that mock STT provider is rejected in development when DEMO_MODE is False."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("STT_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("SECRET_KEY", "valid-dev-secret-key-1234567890123456")

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "STT_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True" in str(exc_info.value)


def test_mock_llm_rejected_without_testing_or_demo_mode(monkeypatch):
    """Verify that mock LLM provider is rejected in development when DEMO_MODE is False."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("STT_PROVIDER", "whisper")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("SECRET_KEY", "valid-dev-secret-key-1234567890123456")

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "LLM_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ready_reports_real_status(client: AsyncClient):
    """Verify that /ready reports real provider names, model loaded flag, and Chroma status."""
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ready"
    assert "llm_provider" in data
    assert "stt_provider" in data
    assert "stt_model_loaded" in data
    assert "chroma_active" in data
    assert "rag_store_mode" in data
    assert data["rag_store_mode"] in ["chromadb", "in_memory_tfidf"]
