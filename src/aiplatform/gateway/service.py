"""GatewayService: provider selection, circuit breaking, and failover."""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog

from aiplatform.gateway.circuit_breaker import CircuitBreaker, CircuitState
from aiplatform.gateway.domain.errors import (
    CircuitOpenError,
    NoHealthyProviderError,
    ProviderAuthError,
    ProviderContextLengthError,
)
from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk
from aiplatform.gateway.domain.ports import LLMProvider
from aiplatform.gateway.providers.registry import ProviderRegistry

logger = structlog.stdlib.get_logger(__name__)

_PERMANENT_ERRORS = (ProviderAuthError, ProviderContextLengthError)


class GatewayService:
    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, provider: LLMProvider) -> CircuitBreaker:
        if provider.name not in self._breakers:
            self._breakers[provider.name] = CircuitBreaker(provider.name)
        return self._breakers[provider.name]

    def _healthy_candidates(self, model: str) -> list[LLMProvider]:
        candidates = self._registry.for_model(model)
        healthy = [p for p in candidates if self._breaker(p).state is not CircuitState.OPEN]
        if not healthy:
            raise NoHealthyProviderError(
                f"All providers for model '{model}' have open circuits",
                context={"model": model},
            )
        return healthy

    async def chat_complete(self, request: ChatRequest) -> ChatResponse:
        candidates = self._healthy_candidates(request.model)
        last_exc: Exception | None = None

        for provider in candidates:
            breaker = self._breaker(provider)
            try:
                response = await breaker.call(provider.complete, request)
                logger.info(
                    "gateway_complete",
                    provider=provider.name,
                    model=request.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
                return response
            except CircuitOpenError:
                logger.warning("gateway_skip_open_circuit", provider=provider.name)
                continue
            except _PERMANENT_ERRORS as exc:
                logger.error(
                    "gateway_permanent_error",
                    provider=provider.name,
                    exc_type=type(exc).__name__,
                )
                raise
            except Exception as exc:
                logger.warning(
                    "gateway_provider_failed",
                    provider=provider.name,
                    exc_type=type(exc).__name__,
                )
                last_exc = exc
                continue

        raise NoHealthyProviderError(
            f"All providers failed for model '{request.model}'",
            context={"model": request.model},
        ) from last_exc

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        candidates = self._healthy_candidates(request.model)
        last_exc: Exception | None = None

        for provider in candidates:
            breaker = self._breaker(provider)
            if breaker.state is CircuitState.OPEN:
                continue
            try:
                chunk_count = 0
                async for chunk in breaker.stream(provider.stream, request):
                    chunk_count += 1
                    yield chunk
                logger.info(
                    "gateway_stream_complete",
                    provider=provider.name,
                    model=request.model,
                    chunks=chunk_count,
                )
                return
            except CircuitOpenError:
                logger.warning("gateway_skip_open_circuit_stream", provider=provider.name)
                continue
            except _PERMANENT_ERRORS as exc:
                logger.error(
                    "gateway_stream_permanent_error",
                    provider=provider.name,
                    exc_type=type(exc).__name__,
                )
                raise
            except Exception as exc:
                logger.warning(
                    "gateway_stream_provider_failed",
                    provider=provider.name,
                    exc_type=type(exc).__name__,
                )
                last_exc = exc
                continue

        raise NoHealthyProviderError(
            f"All providers failed for model '{request.model}'",
            context={"model": request.model},
        ) from last_exc
