"""Google Gemini provider adapter (google-genai SDK)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import structlog
from google import genai  # type: ignore[import-untyped]
from google.genai import types as genai_types  # type: ignore[import-untyped]

from aiplatform.gateway.config import GeminiProviderConfig
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
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
)
from aiplatform.gateway.providers.base import BaseProvider

logger = structlog.stdlib.get_logger(__name__)


def _map_finish_reason(reason: Any) -> FinishReason | None:
    name = str(reason).upper() if reason else ""
    if "MAX_TOKENS" in name:
        return FinishReason.LENGTH
    if "SAFETY" in name:
        return FinishReason.CONTENT_FILTER
    if "STOP" in name or "END" in name:
        return FinishReason.STOP
    return None


def _extract_system(messages: list[Message]) -> str | None:
    for msg in messages:
        if msg.role is MessageRole.SYSTEM:
            return msg.text_content()
    return None


def _to_gemini_contents(messages: list[Message]) -> list[genai_types.Content]:
    return [
        genai_types.Content(
            role="user" if msg.role is MessageRole.USER else "model",
            parts=[genai_types.Part(text=msg.text_content())],
        )
        for msg in messages
        if msg.role is not MessageRole.SYSTEM
    ]


def _wrap_error(exc: Exception) -> ProviderError:
    msg = str(exc).lower()
    if "api_key" in msg or "authentication" in msg or "permission" in msg:
        return ProviderAuthError(str(exc), context={"provider": "gemini"})
    if "quota" in msg or "rate" in msg or "429" in msg:
        return ProviderRateLimitError(str(exc), context={"provider": "gemini"})
    if "timeout" in msg or "deadline" in msg:
        return ProviderTimeoutError(str(exc), context={"provider": "gemini"})
    if "too large" in msg or "context" in msg:
        return ProviderContextLengthError(str(exc), context={"provider": "gemini"})
    return ProviderError(str(exc), context={"provider": "gemini"})


class GeminiProvider(BaseProvider):
    _name = "gemini"

    def __init__(self, config: GeminiProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        if not config.api_key:
            raise ValueError("Gemini provider requires an API key")
        self._client = genai.Client(api_key=config.api_key.get_secret_value())

    def _build_config(self, request: ChatRequest) -> genai_types.GenerateContentConfig:
        kwargs: dict[str, Any] = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_output_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.stop:
            kwargs["stop_sequences"] = request.stop
        system = _extract_system(request.messages)
        if system:
            kwargs["system_instruction"] = system
        return genai_types.GenerateContentConfig(**kwargs)

    async def complete(self, request: ChatRequest) -> ChatResponse:
        contents = _to_gemini_contents(request.messages)
        cfg = self._build_config(request)
        try:
            async for attempt in self._retry:
                with attempt:
                    resp = await self._client.aio.models.generate_content(
                        model=request.model, contents=contents, config=cfg
                    )
        except Exception as exc:
            raise _wrap_error(exc) from exc

        text = resp.text or ""
        usage = TokenUsage()
        if resp.usage_metadata:
            usage = TokenUsage(
                prompt_tokens=resp.usage_metadata.prompt_token_count or 0,
                completion_tokens=resp.usage_metadata.candidates_token_count or 0,
                total_tokens=resp.usage_metadata.total_token_count or 0,
            )
        candidate = resp.candidates[0] if resp.candidates else None
        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=Message(role=MessageRole.ASSISTANT, content=text),
                    finish_reason=_map_finish_reason(
                        candidate.finish_reason if candidate else None
                    ),
                )
            ],
            usage=usage,
            provider=self._name,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        contents = _to_gemini_contents(request.messages)
        cfg = self._build_config(request)
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        try:
            async for chunk in await self._client.aio.models.generate_content_stream(
                model=request.model, contents=contents, config=cfg
            ):
                text = chunk.text or ""
                usage = None
                if chunk.usage_metadata and chunk.usage_metadata.total_token_count:
                    usage = TokenUsage(
                        prompt_tokens=chunk.usage_metadata.prompt_token_count or 0,
                        completion_tokens=chunk.usage_metadata.candidates_token_count or 0,
                        total_tokens=chunk.usage_metadata.total_token_count or 0,
                    )
                yield ChatStreamChunk(
                    id=chunk_id,
                    created=created,
                    model=request.model,
                    choices=[StreamChoice(index=0, delta=StreamDelta(content=text))],
                    usage=usage,
                    provider=self._name,
                )
        except Exception as exc:
            raise _wrap_error(exc) from exc

    async def health(self) -> None:
        try:
            await self._client.aio.models.get(model="gemini-2.0-flash")
        except Exception as exc:
            raise _wrap_error(exc) from exc
