"""Ollama provider adapter (OpenAI-compatible endpoint via httpx)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

import httpx
import structlog

from aiplatform.gateway.config import OllamaProviderConfig
from aiplatform.gateway.domain.errors import ProviderError, ProviderTimeoutError
from aiplatform.gateway.domain.models import (
    ChatChoice,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    Message,
    MessageRole,
    StreamChoice,
    StreamDelta,
    TokenUsage,
)
from aiplatform.gateway.providers.base import BaseProvider
from aiplatform.gateway.providers.openai import _build_kwargs, _map_finish_reason

logger = structlog.stdlib.get_logger(__name__)


def _wrap_error(exc: Exception) -> ProviderError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeoutError(str(exc), context={"provider": "ollama"})
    return ProviderError(str(exc), context={"provider": "ollama"})


class OllamaProvider(BaseProvider):
    _name = "ollama"
    _supported_models = None  # accept any locally available model

    def __init__(self, config: OllamaProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        self._base_url = config.base_url.rstrip("/")

    def _openai_client(self) -> httpx.AsyncClient:
        return self._http_client(base_url=f"{self._base_url}/v1")

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kw = _build_kwargs(request)
        try:
            async for attempt in self._retry:
                with attempt:
                    async with self._openai_client() as client:
                        resp = await client.post("/chat/completions", json=kw)
                        resp.raise_for_status()
                        data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama HTTP {exc.response.status_code}", context={"provider": "ollama"}
            ) from exc
        except Exception as exc:
            raise _wrap_error(exc) from exc

        choice = data["choices"][0]
        msg = choice["message"]
        u = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            created=data.get("created", int(time.time())),
            model=data.get("model", request.model),
            choices=[
                ChatChoice(
                    index=0,
                    message=Message(role=MessageRole(msg["role"]), content=msg.get("content")),
                    finish_reason=_map_finish_reason(choice.get("finish_reason")),
                )
            ],
            usage=TokenUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            ),
            provider=self._name,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        kw = {**_build_kwargs(request), "stream": True}
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        try:
            async with self._openai_client() as client:
                async with client.stream("POST", "/chat/completions", json=kw) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        choices = [
                            StreamChoice(
                                index=c["index"],
                                delta=StreamDelta(content=c["delta"].get("content")),
                                finish_reason=_map_finish_reason(c.get("finish_reason")),
                            )
                            for c in chunk.get("choices", [])
                        ]
                        usage = None
                        if chunk.get("usage"):
                            u = chunk["usage"]
                            usage = TokenUsage(
                                prompt_tokens=u.get("prompt_tokens", 0),
                                completion_tokens=u.get("completion_tokens", 0),
                                total_tokens=u.get("total_tokens", 0),
                            )
                        yield ChatStreamChunk(
                            id=chunk.get("id", chunk_id),
                            created=chunk.get("created", created),
                            model=chunk.get("model", request.model),
                            choices=choices,
                            usage=usage,
                            provider=self._name,
                        )
        except Exception as exc:
            raise _wrap_error(exc) from exc

    async def health(self) -> None:
        try:
            async with self._http_client(base_url=self._base_url) as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
        except Exception as exc:
            raise _wrap_error(exc) from exc
