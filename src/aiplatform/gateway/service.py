"""GatewayService: provider selection, circuit breaking, and failover."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import structlog

from aiplatform.gateway.circuit_breaker import CircuitBreaker, CircuitState
from aiplatform.gateway.domain.errors import (
    CircuitOpenError,
    ModelNotFoundError,
    NoHealthyProviderError,
    ProviderAuthError,
    ProviderContextLengthError,
)
from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk
from aiplatform.gateway.domain.ports import LLMProvider
from aiplatform.gateway.providers.registry import ProviderRegistry
from aiplatform.router.catalog import is_virtual_alias

if TYPE_CHECKING:
    from aiplatform.router.service import RouterService

logger = structlog.stdlib.get_logger(__name__)

_PERMANENT_ERRORS = (ProviderAuthError, ProviderContextLengthError)


class GatewayService:
    def __init__(
        self,
        registry: ProviderRegistry,
        router: RouterService | None = None,
    ) -> None:
        self._registry = registry
        self._router = router
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, provider: LLMProvider) -> CircuitBreaker:
        if provider.name not in self._breakers:
            self._breakers[provider.name] = CircuitBreaker(provider.name)
        return self._breakers[provider.name]

    def _available_provider_names(self) -> list[str]:
        return [
            p.name
            for p in self._registry.all()
            if self._breaker(p).state is not CircuitState.OPEN
        ]

    def _healthy_candidates(self, model: str) -> list[LLMProvider]:
        candidates = self._registry.for_model(model)
        if candidates is None:
            raise ModelNotFoundError(f"No provider registered for model '{model}'")
        healthy = [p for p in candidates if self._breaker(p).state is not CircuitState.OPEN]
        if not healthy:
            raise NoHealthyProviderError(
                f"All providers for model '{model}' have open circuits",
                context={"model": model},
            )
        return healthy

    def _router_candidates(
        self, request: ChatRequest
    ) -> list[tuple[LLMProvider, str]] | None:
        """Return router-ordered (provider, resolved_model_id) pairs, or None to fall back."""
        if self._router is None:
            return None
        try:
            context = self._router.build_context(
                request=request,
                available_providers=self._available_provider_names(),
            )
            decision = self._router.select(context)
        except Exception:
            return None
        result: list[tuple[LLMProvider, str]] = []
        for provider_name, model_id in decision.candidates:
            provider = self._registry.get(provider_name)
            if provider and self._breaker(provider).state is not CircuitState.OPEN:
                result.append((provider, model_id))
        return result or None

    async def chat_complete(self, request: ChatRequest) -> ChatResponse:
        router_pairs = self._router_candidates(request)
        last_exc: Exception | None = None

        if router_pairs is not None:
            for provider, model_id in router_pairs:
                breaker = self._breaker(provider)
                resolved = request.model_copy(update={"model": model_id})
                t0 = time.monotonic()
                try:
                    response = await breaker.call(provider.complete, resolved)
                    elapsed_ms = (time.monotonic() - t0) * 1_000
                    if self._router is not None:
                        self._router.record_latency(model_id, elapsed_ms)
                    logger.info(
                        "gateway_complete",
                        provider=provider.name,
                        model=model_id,
                        latency_ms=round(elapsed_ms),
                    )
                    return response
                except CircuitOpenError:
                    logger.warning("gateway_skip_open_circuit", provider=provider.name)
                    continue
                except _PERMANENT_ERRORS as exc:
                    logger.error("gateway_permanent_error", provider=provider.name, exc_type=type(exc).__name__)
                    raise
                except Exception as exc:
                    logger.warning("gateway_provider_failed", provider=provider.name, exc_type=type(exc).__name__)
                    last_exc = exc
                    continue
        else:
            for provider in self._healthy_candidates(request.model):
                breaker = self._breaker(provider)
                try:
                    response = await breaker.call(provider.complete, request)
                    logger.info("gateway_complete", provider=provider.name, model=request.model)
                    return response
                except CircuitOpenError:
                    logger.warning("gateway_skip_open_circuit", provider=provider.name)
                    continue
                except _PERMANENT_ERRORS as exc:
                    logger.error("gateway_permanent_error", provider=provider.name, exc_type=type(exc).__name__)
                    raise
                except Exception as exc:
                    logger.warning("gateway_provider_failed", provider=provider.name, exc_type=type(exc).__name__)
                    last_exc = exc
                    continue

        raise NoHealthyProviderError(
            f"All providers failed for model '{request.model}'",
            context={"model": request.model},
        ) from last_exc

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        router_pairs = self._router_candidates(request)
        last_exc: Exception | None = None

        pairs: list[tuple[LLMProvider, ChatRequest]]
        if router_pairs is not None:
            pairs = [(p, request.model_copy(update={"model": mid})) for p, mid in router_pairs]
        else:
            pairs = [(p, request) for p in self._healthy_candidates(request.model)]

        for provider, resolved in pairs:
            breaker = self._breaker(provider)
            if breaker.state is CircuitState.OPEN:
                continue
            try:
                chunk_count = 0
                async for chunk in breaker.stream(provider.stream, resolved):
                    chunk_count += 1
                    yield chunk
                logger.info(
                    "gateway_stream_complete",
                    provider=provider.name,
                    model=resolved.model,
                    chunks=chunk_count,
                )
                return
            except CircuitOpenError:
                logger.warning("gateway_skip_open_circuit_stream", provider=provider.name)
                continue
            except _PERMANENT_ERRORS as exc:
                logger.error("gateway_stream_permanent_error", provider=provider.name, exc_type=type(exc).__name__)
                raise
            except Exception as exc:
                logger.warning("gateway_stream_provider_failed", provider=provider.name, exc_type=type(exc).__name__)
                last_exc = exc
                continue

        raise NoHealthyProviderError(
            f"All providers failed for model '{request.model}'",
            context={"model": request.model},
        ) from last_exc
