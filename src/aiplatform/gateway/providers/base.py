"""Shared utilities for provider adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
import tenacity

from aiplatform.gateway.domain.errors import (
    ProviderAuthError,
    ProviderContextLengthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ProviderRateLimitError | ProviderTimeoutError):
        return True
    if isinstance(exc, ProviderAuthError | ProviderContextLengthError):
        return False
    if isinstance(exc, ProviderError):
        return True
    if isinstance(exc, httpx.TimeoutException | httpx.NetworkError):
        return True
    return False


def build_retry(max_attempts: int, provider_name: str) -> tenacity.AsyncRetrying:
    return tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception(_is_retryable),
        wait=tenacity.wait_exponential(multiplier=0.5, min=0.5, max=30.0),
        stop=tenacity.stop_after_attempt(max_attempts),
        before_sleep=tenacity.before_sleep_log(
            structlog.stdlib.get_logger(f"aiplatform.gateway.{provider_name}"),
            structlog.stdlib.logging.WARNING,
        ),
        reraise=True,
    )


class BaseProvider:
    _name: str = ""
    _supported_models: frozenset[str] | None = None

    def __init__(self, *, timeout: float, max_retries: int) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._log = structlog.stdlib.get_logger(f"aiplatform.gateway.{self._name}")
        self._retry = build_retry(max_retries, self._name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_models(self) -> frozenset[str] | None:
        return self._supported_models

    def _http_client(self, base_url: str = "", **kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(self._timeout),
            **kwargs,
        )

    async def complete(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        raise NotImplementedError
        if False:  # pragma: no cover
            yield  # type: ignore[misc]

    async def health(self) -> None:
        raise NotImplementedError
