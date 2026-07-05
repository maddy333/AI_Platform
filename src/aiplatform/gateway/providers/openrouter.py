"""OpenRouter provider adapter (OpenAI-compatible API with attribution headers)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import openai

from aiplatform.gateway.config import OpenRouterProviderConfig
from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk
from aiplatform.gateway.providers.base import BaseProvider
from aiplatform.gateway.providers.openai import OpenAIProvider, _wrap_error

_REQUIRED_HEADERS = {
    "HTTP-Referer": "https://github.com/ai-platform/ai-platform",
    "X-Title": "AI Platform",
}


class OpenRouterProvider(BaseProvider):
    _name = "openrouter"
    _supported_models = None  # pass-through to openrouter's catalogue

    def __init__(self, config: OpenRouterProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        if not config.api_key:
            raise ValueError("OpenRouter provider requires an API key")
        self._oai = openai.AsyncOpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout,
            max_retries=0,
            default_headers=_REQUIRED_HEADERS,
        )
        self._inner = _OpenRouterDelegate(self._oai, config.timeout, config.max_retries)

    async def complete(self, request: ChatRequest) -> ChatResponse:
        resp = await self._inner.complete(request)
        resp.provider = self._name
        return resp

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        async for chunk in self._inner.stream(request):
            chunk.provider = self._name
            yield chunk

    async def health(self) -> None:
        try:
            await self._oai.models.list()
        except Exception as exc:
            err = _wrap_error(exc)
            err.context["provider"] = "openrouter"
            raise err from exc


class _OpenRouterDelegate(OpenAIProvider):
    _name = "openrouter_delegate"

    def __init__(self, client: openai.AsyncOpenAI, timeout: float, max_retries: int) -> None:
        BaseProvider.__init__(self, timeout=timeout, max_retries=max_retries)
        self._oai = client
