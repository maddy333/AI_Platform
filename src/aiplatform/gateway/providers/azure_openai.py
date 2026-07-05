"""Azure OpenAI provider adapter.

Azure OpenAI uses the same API surface as OpenAI but routes through a
tenant-specific endpoint with an api-version query parameter.
Deployment names serve as model identifiers.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator

import openai

from aiplatform.gateway.config import AzureOpenAIProviderConfig
from aiplatform.gateway.domain.models import (
    ChatChoice,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    FunctionCall,
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
    ToolCall,
)
from aiplatform.gateway.providers.base import BaseProvider
from aiplatform.gateway.providers.openai import _build_kwargs, _map_finish_reason, _wrap_error


class AzureOpenAIProvider(BaseProvider):
    _name = "azure_openai"

    def __init__(self, config: AzureOpenAIProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        if not config.api_key or not config.endpoint:
            raise ValueError("Azure OpenAI provider requires api_key and endpoint")
        self._oai = openai.AsyncAzureOpenAI(
            api_key=config.api_key.get_secret_value(),
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
            timeout=config.timeout,
            max_retries=0,
        )

    def _rewrap(self, exc: Exception) -> Exception:
        err = _wrap_error(exc)
        err.context["provider"] = "azure_openai"
        return err

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kw = _build_kwargs(request)
        try:
            async for attempt in self._retry:
                with attempt:
                    resp = await self._oai.chat.completions.create(**kw)
        except Exception as exc:
            raise self._rewrap(exc) from exc

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
            raise self._rewrap(exc) from exc

    async def health(self) -> None:
        try:
            await self._oai.models.list()
        except Exception as exc:
            raise self._rewrap(exc) from exc
