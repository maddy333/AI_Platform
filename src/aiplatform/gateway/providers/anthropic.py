"""Anthropic provider adapter."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import anthropic
import structlog

from aiplatform.gateway.config import AnthropicProviderConfig
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


def _map_finish_reason(stop_reason: str | None) -> FinishReason | None:
    return {
        "end_turn": FinishReason.STOP,
        "max_tokens": FinishReason.LENGTH,
        "tool_use": FinishReason.TOOL_CALLS,
        "stop_sequence": FinishReason.STOP,
    }.get(stop_reason or "")


def _extract_system(messages: list[Message]) -> tuple[str | None, list[Message]]:
    if messages and messages[0].role is MessageRole.SYSTEM:
        return messages[0].text_content() or None, messages[1:]
    return None, messages


def _to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role is MessageRole.TOOL:
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.text_content(),
                        }
                    ],
                }
            )
        elif msg.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments),
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
        else:
            role = "user" if msg.role is MessageRole.USER else "assistant"
            content: Any = msg.text_content()
            if isinstance(msg.content, list):
                content = [p.model_dump() for p in msg.content]
            out.append({"role": role, "content": content})
    return out


def _wrap_error(exc: Exception) -> ProviderError:
    if isinstance(exc, anthropic.AuthenticationError):
        return ProviderAuthError(str(exc), context={"provider": "anthropic"})
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderRateLimitError(str(exc), context={"provider": "anthropic"})
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderTimeoutError(str(exc), context={"provider": "anthropic"})
    if isinstance(exc, anthropic.BadRequestError) and "too many" in str(exc).lower():
        return ProviderContextLengthError(str(exc), context={"provider": "anthropic"})
    return ProviderError(str(exc), context={"provider": "anthropic"})


class AnthropicProvider(BaseProvider):
    _name = "anthropic"

    def __init__(self, config: AnthropicProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        if not config.api_key:
            raise ValueError("Anthropic provider requires an API key")
        self._client = anthropic.AsyncAnthropic(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,
        )

    def _build_kwargs(self, request: ChatRequest) -> dict[str, Any]:
        system, turns = _extract_system(request.messages)
        kw: dict[str, Any] = {
            "model": request.model,
            "messages": _to_anthropic_messages(turns),
            "max_tokens": request.max_tokens or 4096,
        }
        if system:
            kw["system"] = system
        if request.temperature is not None:
            kw["temperature"] = request.temperature
        if request.top_p is not None:
            kw["top_p"] = request.top_p
        if request.stop:
            kw["stop_sequences"] = request.stop
        if request.tools:
            kw["tools"] = [
                {
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "input_schema": t.function.parameters,
                }
                for t in request.tools
            ]
        return kw

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kw = self._build_kwargs(request)
        try:
            async for attempt in self._retry:
                with attempt:
                    resp = await self._client.messages.create(**kw)
        except Exception as exc:
            raise _wrap_error(exc) from exc

        content = ""
        tool_calls: list[ToolCall] | None = None
        for block in resp.content:
            if hasattr(block, "text"):
                content += block.text
            elif block.type == "tool_use":
                tool_calls = tool_calls or []
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        function=FunctionCall(
                            name=block.name,
                            arguments=json.dumps(block.input),
                        ),
                    )
                )
        usage = TokenUsage(
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
        )
        return ChatResponse(
            id=resp.id,
            created=int(time.time()),
            model=resp.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=Message(
                        role=MessageRole.ASSISTANT,
                        content=content or None,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=_map_finish_reason(resp.stop_reason),
                )
            ],
            usage=usage,
            provider=self._name,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        kw = self._build_kwargs(request)
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        try:
            async with self._client.messages.stream(**kw) as s:
                async for text in s.text_stream:
                    yield ChatStreamChunk(
                        id=chunk_id,
                        created=created,
                        model=request.model,
                        choices=[StreamChoice(index=0, delta=StreamDelta(content=text))],
                        provider=self._name,
                    )
                final = await s.get_final_message()
                usage = TokenUsage(
                    prompt_tokens=final.usage.input_tokens,
                    completion_tokens=final.usage.output_tokens,
                    total_tokens=final.usage.input_tokens + final.usage.output_tokens,
                )
                yield ChatStreamChunk(
                    id=chunk_id,
                    created=created,
                    model=request.model,
                    choices=[
                        StreamChoice(
                            index=0,
                            delta=StreamDelta(),
                            finish_reason=_map_finish_reason(final.stop_reason),
                        )
                    ],
                    usage=usage,
                    provider=self._name,
                )
        except Exception as exc:
            raise _wrap_error(exc) from exc

    async def health(self) -> None:
        try:
            await self._client.models.list()
        except Exception as exc:
            raise _wrap_error(exc) from exc
