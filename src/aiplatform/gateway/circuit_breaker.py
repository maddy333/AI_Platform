"""Async circuit breaker — per-provider, three-state automaton.

States
------
CLOSED    Normal operation. Failures are counted; once ``failure_threshold``
          consecutive failures occur the breaker trips to OPEN.
OPEN      Fast-fail. All calls raise ``CircuitOpenError`` without touching
          the provider. After ``recovery_timeout`` seconds one probe is
          allowed through (transitions to HALF_OPEN).
HALF_OPEN One call is in flight. Success → CLOSED; failure → OPEN.

Thread-safety: asyncio.Lock guards every state transition.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from enum import StrEnum
from typing import Any, TypeVar

import structlog

from aiplatform.gateway.domain.errors import CircuitOpenError

logger = structlog.stdlib.get_logger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Async three-state circuit breaker."""

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
    ) -> None:
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute ``fn`` guarded by the circuit breaker."""
        async with self._lock:
            await self._maybe_probe()
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit is open for provider '{self.name}'",
                    context={"provider": self.name, "state": self._state},
                )
        try:
            result: T = await fn(*args, **kwargs)
        except Exception as exc:
            async with self._lock:
                await self._record_failure(exc)
            raise
        else:
            async with self._lock:
                await self._record_success()
            return result

    async def stream(
        self,
        fn: Callable[..., AsyncIterator[T]],
        *args: Any,
        **kwargs: Any,
    ) -> AsyncIterator[T]:
        """Stream variant — circuit breaker wrapping an async generator."""
        async with self._lock:
            await self._maybe_probe()
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit is open for provider '{self.name}'",
                    context={"provider": self.name, "state": self._state},
                )
        try:
            async for chunk in fn(*args, **kwargs):
                yield chunk
        except Exception as exc:
            async with self._lock:
                await self._record_failure(exc)
            raise
        else:
            async with self._lock:
                await self._record_success()

    async def _maybe_probe(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            logger.info("circuit_half_open", provider=self.name)

    async def _record_success(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._opened_at = None
                logger.info("circuit_closed", provider=self.name)
        elif self._state is CircuitState.CLOSED:
            self._failure_count = 0

    async def _record_failure(self, exc: Exception) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning("circuit_reopened", provider=self.name, exc_type=type(exc).__name__)
        elif self._state is CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    "circuit_opened",
                    provider=self.name,
                    failures=self._failure_count,
                    exc_type=type(exc).__name__,
                )
