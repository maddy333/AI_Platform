"""Unit tests for the gateway API router (/v1/chat/completions, /v1/models)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from aiplatform.gateway.domain.models import (
    ChatChoice,
    ChatResponse,
    ChatStreamChunk,
    FinishReason,
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(model: str = "gpt-4o") -> ChatResponse:
    return ChatResponse(
        id="chatcmpl-test",
        model=model,
        choices=[
            ChatChoice(
                index=0,
                message=Message(role=MessageRole.ASSISTANT, content="Hello!"),
                finish_reason=FinishReason.STOP,
            )
        ],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )


def _make_chunk(content: str = "Hi") -> ChatStreamChunk:
    return ChatStreamChunk(
        id="chatcmpl-test",
        model="gpt-4o",
        choices=[
            StreamChoice(
                index=0,
                delta=StreamDelta(role=MessageRole.ASSISTANT, content=content),
                finish_reason=None,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_service() -> MagicMock:
    svc = MagicMock()
    svc.chat_complete = AsyncMock(return_value=_make_response())
    svc._registry = MagicMock()
    svc._registry.all.return_value = []
    return svc


@pytest.fixture()
def client(mock_service: MagicMock) -> TestClient:
    from aiplatform.app import create_app
    from aiplatform.core.config import Settings

    settings = Settings(environment="test")  # type: ignore[call-arg]
    app = create_app(settings)
    app.state.gateway = mock_service
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — JSON mode
# ---------------------------------------------------------------------------


def test_chat_completions_200(client: TestClient, mock_service: MagicMock) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "gpt-4o"
    assert body["choices"][0]["message"]["content"] == "Hello!"
    mock_service.chat_complete.assert_awaited_once()


def test_chat_completions_422_empty_messages(client: TestClient) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": []},
    )
    assert resp.status_code == 422


def test_chat_completions_422_missing_model(client: TestClient) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 422


def test_chat_completions_422_temperature_out_of_range(client: TestClient) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 5.0,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — SSE streaming
# ---------------------------------------------------------------------------


def test_chat_completions_stream_sse(client: TestClient, mock_service: MagicMock) -> None:
    chunks = [_make_chunk("Hello"), _make_chunk(" world")]

    async def _stream(_req):  # type: ignore[no-untyped-def]
        for chunk in chunks:
            yield chunk

    mock_service.chat_stream = _stream

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        raw = resp.read().decode()

    assert "data:" in raw
    assert "[DONE]" in raw


# ---------------------------------------------------------------------------
# GET /v1/models
# ---------------------------------------------------------------------------


def test_list_models_empty(client: TestClient, mock_service: MagicMock) -> None:
    mock_service._registry.all.return_value = []
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert body["data"] == []


def test_list_models_with_fixed_model_set(client: TestClient, mock_service: MagicMock) -> None:
    p = MagicMock()
    p.name = "openai"
    p.supported_models = {"gpt-4o", "gpt-4o-mini"}
    mock_service._registry.all.return_value = [p]

    resp = client.get("/v1/models")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert "gpt-4o" in ids
    assert "gpt-4o-mini" in ids


def test_list_models_wildcard_for_open_ended_provider(
    client: TestClient, mock_service: MagicMock
) -> None:
    p = MagicMock()
    p.name = "ollama"
    p.supported_models = None
    mock_service._registry.all.return_value = [p]

    resp = client.get("/v1/models")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert "ollama/*" in ids
