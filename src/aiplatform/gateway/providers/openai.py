"""OpenAI provider adapter."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import openai
import structlog

from aiplatform.gateway.config import OpenAIProviderConfig
from aiplatform.gateway.domain.errors import (
    ProviderAuthError,
    ProviderContextLengthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from aiplatform.gateway.domain.models import (
    ChatChoice,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    FinishReason,
    FunctionCall,
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
    ToolCall,
)
from aiplatform.gateway.providers.base import BaseProvider

logger = structlog.stdlib.get_logger(__name__)


def _map_finish_reason(reason: str | None) -> FinishReason | None:
    return {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "tool_calls": FinishReason.TOOL_CALLS,
        "content_filter": FinishReason.CONTENT_FILTER,
    }.get(reason or "")


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        d: dict[str, Any] = {"role": msg.role.value}
        if isinstance(msg.content, str):
            d["content"] = msg.content
        elif isinstance(msg.content, list):
            d["content"] = [p.model_dump() for p in msg.content]
        else:
            d["content"] = None
        if msg.name:
            d["name"] = msg.name
        if msg.tool_calls:
            d["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        out.append(d)
    return out


def _build_kwargs(request: ChatRequest) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "model": request.model,
        "messages": _to_openai_messages(request.messages),
    }
    if request.temperature is not None:
        kw["temperature"] = request.temperature
    if request.max_tokens is not None:
        kw["max_tokens"] = request.max_tokens
    if request.top_p is not None:
        kw["top_p"] = request.top_p
    if request.frequency_penalty is not None:
        kw["frequency_penalty"] = request.frequency_penalty
    if request.presence_penalty is not None:
        kw["presence_penalty"] = request.presence_penalty
    if request.stop:
        kw["stop"] = request.stop
    if request.seed is not None:
        kw["seed"] = request.seed
    if request.user:
        kw["user"] = request.user
    if request.tools:
        kw["tools"] = [t.model_dump() for t in request.tools]
    if request.tool_choice is not None:
        kw["tool_choice"] = request.tool_choice
    if request.response_format is not None:
        kw["response_format"] = request.response_format.model_dump(exclude_none=True)
    return kw


def _wrap_error(exc: Exception) -> ProviderError:
    if isinstance(exc, openai.AuthenticationError):
        return ProviderAuthError(str(exc), context={"provider": "openai"})
    if isinstance(exc, openai.RateLimitError):
        return ProviderRateLimitError(str(exc), context={"provider": "openai"})
    if isinstance(exc, openai.APITimeoutError):
        return ProviderTimeoutError(str(exc), context={"provider": "openai"})
    if isinstance(exc, openai.BadRequestError) and "context_length" in str(exc).lower():
        return ProviderContextLengthError(str(exc), context={"provider": "openai"})
    return ProviderError(str(exc), context={"provider": "openai"})


class OpenAIProvider(BaseProvider):
    _name = "openai"

    def __init__(self, config: OpenAIProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        if not config.api_key:
            raise ValueError("OpenAI provider requires an API key")
        self._oai = openai.AsyncOpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,
        )

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kw = _build_kwargs(request)
        try:
            async for attempt in self._retry:
                with attempt:
                    resp = await self._oai.chat.completions.create(**kw)
        except Exception as exc:
            raise _wrap_error(exc) from exc

        choice = resp.choices[0]
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function=FunctionCall(name=tc.function.name, arguments=tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]
        usage = TokenUsage()
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
            )
        return ChatResponse(
            id=resp.id,
            created=resp.created,
            model=resp.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=Message(
                        role=MessageRole(choice.message.role),
                        content=choice.message.content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=_map_finish_reason(choice.finish_reason),
                )
            ],
            usage=usage,
            provider=self._name,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        kw = {**_build_kwargs(request), "stream": True, "stream_options": {"include_usage": True}}
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        try:
            async with self._oai.chat.completions.stream(**kw) as s:
                async for chunk in s:
                    choices = [
                        StreamChoice(
                            index=c.index,
                            delta=StreamDelta(
                                role=MessageRole(c.delta.role) if c.delta.role else None,
                                content=c.delta.content,
                            ),
                            finish_reason=_map_finish_reason(c.finish_reason),
                        )
                        for c in chunk.choices
                    ]
                    usage = None
                    if chunk.usage:
                        usage = TokenUsage(
                            prompt_tokens=chunk.usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens,
                        )
                    yield ChatStreamChunk(
                        id=chunk.id or chunk_id,
                        created=chunk.created or created,
                        model=chunk.model or request.model,
                        choices=choices,
                        usage=usage,
                        provider=self._name,
                    )
        except Exception as exc:
            raise _wrap_error(exc) from exc

    async def health(self) -> None:
        try:
            await self._oai.models.list()
        except Exception as exc:
            raise _wrap_error(exc) from exc
