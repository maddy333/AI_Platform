"""vLLM provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import openai

from aiplatform.gateway.config import VLLMProviderConfig
from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk
from aiplatform.gateway.providers.base import BaseProvider
from aiplatform.gateway.providers.openai import OpenAIProvider, _wrap_error


class VLLMProvider(BaseProvider):
    _name = "vllm"
    _supported_models = None  # determined by vLLM server config

    def __init__(self, config: VLLMProviderConfig) -> None:
        super().__init__(timeout=config.timeout, max_retries=config.max_retries)
        api_key = config.api_key.get_secret_value() if config.api_key else "vllm"
        self._oai = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url.rstrip("/") + "/v1",
            timeout=config.timeout,
            max_retries=0,
        )
        self._inner = _VLLMDelegate(self._oai, config.timeout, config.max_retries)

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
            err.context["provider"] = "vllm"
            raise err from exc


class _VLLMDelegate(OpenAIProvider):
    """Reuse OpenAI adapter with an injected client; skip OpenAI's __init__."""

    _name = "vllm_delegate"

    def __init__(self, client: openai.AsyncOpenAI, timeout: float, max_retries: int) -> None:
        BaseProvider.__init__(self, timeout=timeout, max_retries=max_retries)
        self._oai = client
