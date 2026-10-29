"""LLM provider tests against canned HTTP responses (no network, no GPU)."""

import json
from typing import Callable, List

import httpx
import pytest

from app.core.config import settings
from app.services.llm import get_llm_provider
from app.services.llm.base import BaseLLMProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.grok import GrokProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.ollama import OllamaProvider

Handler = Callable[[httpx.Request], httpx.Response]


def recording_transport(handler: Handler, seen: List[httpx.Request]) -> httpx.MockTransport:
    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(wrapped)


def no_backoff(provider: BaseLLMProvider) -> BaseLLMProvider:
    provider.backoff_base_seconds = 0
    return provider


def sse(*events: dict, done: bool = False) -> bytes:
    lines = [f"data: {json.dumps(e)}\n\n" for e in events]
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


# --------------------------------------------------------------------------- Ollama


async def test_ollama_text_json_and_system_prompt() -> None:
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("format") == "json":
            return httpx.Response(200, json={"response": '```json\n{"score_0_10": 7}\n```'})
        return httpx.Response(200, json={"response": "  Explain deadlock.  "})

    provider = OllamaProvider(
        base_url="http://ollama:11434/", model="qwen2.5:3b", transport=recording_transport(handler, seen)
    )

    assert await provider.generate_text("q", system="be calm") == "Explain deadlock."
    assert await provider.generate_json("grade") == {"score_0_10": 7}

    first = json.loads(seen[0].content)
    assert str(seen[0].url) == "http://ollama:11434/api/generate"
    assert first == {"model": "qwen2.5:3b", "prompt": "q", "stream": False, "system": "be calm"}


async def test_ollama_stream_yields_tokens_until_done() -> None:
    lines = [{"response": "Dead"}, {"response": "lock"}, {"response": "", "done": True}, {"response": "ignored"}]
    body = "\n".join(json.dumps(line) for line in lines).encode()
    provider = OllamaProvider(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))

    assert [t async for t in provider.generate_stream("q")] == ["Dead", "lock"]


async def test_retries_transient_errors_then_succeeds() -> None:
    responses = iter(
        [httpx.Response(503, text="busy"), httpx.Response(429), httpx.Response(200, json={"response": "ok"})]
    )
    seen: List[httpx.Request] = []
    provider = no_backoff(OllamaProvider(transport=recording_transport(lambda r: next(responses), seen)))

    assert await provider.generate_text("q") == "ok"
    assert len(seen) == 3


async def test_does_not_retry_client_errors() -> None:
    seen: List[httpx.Request] = []
    provider = no_backoff(
        OllamaProvider(transport=recording_transport(lambda r: httpx.Response(404, text="no model"), seen))
    )

    with pytest.raises(RuntimeError, match="404"):
        await provider.generate_text("q")
    assert len(seen) == 1


async def test_gives_up_after_max_retries_on_connection_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = no_backoff(OllamaProvider(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="unreachable"):
        await provider.generate_text("q")


# --------------------------------------------------------------------------- Gemini


def gemini_body(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


async def test_gemini_sends_key_in_header_not_url() -> None:
    seen: List[httpx.Request] = []
    provider = GeminiProvider(
        api_key="secret-key",
        model="gemini-2.0-flash",
        transport=recording_transport(lambda r: httpx.Response(200, json=gemini_body(" Hello ")), seen),
    )

    assert await provider.generate_text("hi", system="examiner") == "Hello"
    request = seen[0]
    assert "secret-key" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "secret-key"
    assert json.loads(request.content)["systemInstruction"] == {"parts": [{"text": "examiner"}]}


async def test_gemini_json_mode_and_empty_candidates() -> None:
    seen: List[httpx.Request] = []
    replies = iter(
        [httpx.Response(200, json=gemini_body('{"topic": "Paging"}')), httpx.Response(200, json={"candidates": []})]
    )
    provider = GeminiProvider(api_key="k", transport=recording_transport(lambda r: next(replies), seen))

    assert await provider.generate_json("q") == {"topic": "Paging"}
    assert json.loads(seen[0].content)["generationConfig"] == {"responseMimeType": "application/json"}
    with pytest.raises(RuntimeError, match="no candidate text"):
        await provider.generate_text("q")


async def test_gemini_streams_server_sent_events() -> None:
    body = sse(gemini_body("Dead"), gemini_body("lock"))
    seen: List[httpx.Request] = []
    provider = GeminiProvider(
        api_key="k", transport=recording_transport(lambda r: httpx.Response(200, content=body), seen)
    )

    assert [t async for t in provider.generate_stream("q")] == ["Dead", "lock"]
    assert seen[0].url.path.endswith(":streamGenerateContent")
    assert seen[0].url.params["alt"] == "sse"


async def test_gemini_requires_api_key() -> None:
    provider = GeminiProvider(api_key="", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    provider.api_key = ""
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await provider.generate_text("q")


# --------------------------------------------------------------------------- Grok


def grok_body(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


async def test_grok_text_and_json_mode() -> None:
    seen: List[httpx.Request] = []
    replies = iter([httpx.Response(200, json=grok_body(" Hi ")), httpx.Response(200, json=grok_body('{"a": 1}'))])
    provider = GrokProvider(
        api_key="xai-key", model="grok-2", transport=recording_transport(lambda r: next(replies), seen)
    )

    assert await provider.generate_text("q", system="sys") == "Hi"
    assert await provider.generate_json("q") == {"a": 1}

    assert seen[0].headers["Authorization"] == "Bearer xai-key"
    assert json.loads(seen[0].content)["messages"][0] == {"role": "system", "content": "sys"}
    assert json.loads(seen[1].content)["response_format"] == {"type": "json_object"}


async def test_grok_streams_deltas() -> None:
    body = sse(
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Dead"}}]},
        {"choices": [{"delta": {"content": "lock"}}]},
        done=True,
    )
    provider = GrokProvider(api_key="k", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))
    assert [t async for t in provider.generate_stream("q")] == ["Dead", "lock"]


async def test_grok_stream_error_status() -> None:
    provider = GrokProvider(api_key="k", transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(RuntimeError, match="401"):
        _ = [t async for t in provider.generate_stream("q")]


# --------------------------------------------------------------------------- Factory & JSON cleaning


@pytest.mark.parametrize(
    ("name", "cls"),
    [("ollama", OllamaProvider), ("gemini", GeminiProvider), ("grok", GrokProvider), ("mock", MockLLMProvider)],
)
def test_factory_selects_provider_from_config(name: str, cls: type) -> None:
    assert isinstance(get_llm_provider(force_provider=name), cls)


def test_factory_refuses_mock_outside_testing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(RuntimeError, match="only permitted"):
        get_llm_provider(force_provider="mock")


@pytest.mark.parametrize(
    "raw",
    ['{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', 'Sure! Here you go: {"a": 1} Hope that helps.'],
)
def test_clean_json_string_variants(raw: str) -> None:
    assert MockLLMProvider().clean_json_string(raw) == {"a": 1}


def test_clean_json_string_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="Could not parse"):
        MockLLMProvider().clean_json_string("no json {here")
