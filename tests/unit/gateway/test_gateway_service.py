"""Unit tests for GatewayService — failover, routing, circuit breaker integration."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiplatform.gateway.domain.errors import (
    ModelNotFoundError,
    NoHealthyProviderError,
    ProviderAuthError,
    ProviderError,
)
from aiplatform.gateway.domain.models import (
    ChatChoice,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    FinishReason,
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
)
from aiplatform.gateway.providers.registry import ProviderRegistry
from aiplatform.gateway.service import GatewayService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(model: str = "gpt-4o") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role=MessageRole.USER, content="ping")],
    )


def _make_response(model: str = "gpt-4o") -> ChatResponse:
    return ChatResponse(
        id=str(uuid.uuid4()),
        model=model,
        choices=[
            ChatChoice(
                index=0,
                message=Message(role=MessageRole.ASSISTANT, content="pong"),
                finish_reason=FinishReason.STOP,
            )
        ],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
    )


def _make_chunk(model: str = "gpt-4o") -> ChatStreamChunk:
    return ChatStreamChunk(
        id=str(uuid.uuid4()),
        model=model,
        choices=[
            StreamChoice(
                index=0,
                delta=StreamDelta(role=MessageRole.ASSISTANT, content="po"),
                finish_reason=None,
            )
        ],
    )


def _mock_provider(
    name: str,
    models: set[str] | None = None,
    response: ChatResponse | None = None,
    fail_with: Exception | None = None,
) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.supported_models = models
    p.health = AsyncMock(return_value=True)
    if fail_with is not None:
        p.complete = AsyncMock(side_effect=fail_with)
    else:
        p.complete = AsyncMock(return_value=response or _make_response(name))
    return p


def _mock_streaming_provider(
    name: str,
    chunks: list[ChatStreamChunk],
    models: set[str] | None = None,
) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.supported_models = models
    p.health = AsyncMock(return_value=True)
    p.complete = AsyncMock(return_value=_make_response(name))

    async def _stream(_req: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        for chunk in chunks:
            yield chunk

    p.stream = _stream
    return p


def _registry(*providers) -> ProviderRegistry:
    reg = ProviderRegistry()
    for prov in providers:
        reg.register(prov)
    return reg


# ---------------------------------------------------------------------------
# chat_complete — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_complete_returns_response() -> None:
    expected = _make_response()
    provider = _mock_provider("openai", models={"gpt-4o"}, response=expected)
    service = GatewayService(_registry(provider))
    result = await service.chat_complete(_make_request())
    assert result is expected
    provider.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_complete_selects_by_model() -> None:
    openai = _mock_provider("openai", models={"gpt-4o"})
    anthropic = _mock_provider("anthropic", models={"claude-3-5-sonnet-20241022"})
    service = GatewayService(_registry(openai, anthropic))
    await service.chat_complete(_make_request("claude-3-5-sonnet-20241022"))
    anthropic.complete.assert_awaited_once()
    openai.complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# chat_complete — failover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_complete_fails_over_to_next_provider() -> None:
    p1 = _mock_provider("p1", models=None, fail_with=ProviderError("down", provider="p1"))
    p2 = _mock_provider("p2", models=None)
    service = GatewayService(_registry(p1, p2))
    result = await service.chat_complete(_make_request())
    assert result is not None
    p2.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_complete_raises_no_healthy_when_all_fail() -> None:
    p1 = _mock_provider("p1", models=None, fail_with=ProviderError("down", provider="p1"))
    service = GatewayService(_registry(p1))
    with pytest.raises(NoHealthyProviderError):
        await service.chat_complete(_make_request())


@pytest.mark.asyncio
async def test_chat_complete_raises_model_not_found() -> None:
    provider = _mock_provider("openai", models={"gpt-4o"})
    service = GatewayService(_registry(provider))
    with pytest.raises(ModelNotFoundError):
        await service.chat_complete(_make_request("unknown-model-xyz"))


@pytest.mark.asyncio
async def test_chat_complete_no_failover_on_auth_error() -> None:
    p1 = _mock_provider("p1", models=None, fail_with=ProviderAuthError("bad key", provider="p1"))
    p2 = _mock_provider("p2", models=None)
    service = GatewayService(_registry(p1, p2))
    with pytest.raises((ProviderAuthError, NoHealthyProviderError)):
        await service.chat_complete(_make_request())
    p2.complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# chat_stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks() -> None:
    chunks = [_make_chunk(), _make_chunk()]
    provider = _mock_streaming_provider("openai", chunks=chunks, models=None)
    service = GatewayService(_registry(provider))
    collected = [chunk async for chunk in service.chat_stream(_make_request())]
    assert len(collected) == 2


@pytest.mark.asyncio
async def test_chat_stream_raises_when_all_providers_fail() -> None:
    p = MagicMock()
    p.name = "p1"
    p.supported_models = None
    p.health = AsyncMock(return_value=True)

    async def _bad_stream(_req: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        raise ProviderError("down", provider="p1")
        yield  # noqa: unreachable — makes this an async generator

    p.stream = _bad_stream
    service = GatewayService(_registry(p))
    with pytest.raises((ProviderError, NoHealthyProviderError)):
        async for _ in service.chat_stream(_make_request()):
            pass
