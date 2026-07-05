"""Unit tests for the async circuit breaker."""

from __future__ import annotations

import time

import pytest

from aiplatform.gateway.circuit_breaker import CircuitBreaker, CircuitState
from aiplatform.gateway.domain.errors import CircuitOpenError, ProviderError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_breaker(
    failure_threshold: int = 3,
    recovery_timeout: float = 60.0,
    half_open_max: int = 1,
) -> CircuitBreaker:
    return CircuitBreaker(
        name="test",
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        half_open_max=half_open_max,
    )


async def _ok() -> str:
    return "ok"


async def _fail() -> str:
    raise ProviderError("boom", provider="test")


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initial_state_is_closed() -> None:
    breaker = _make_breaker()
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_successful_calls_remain_closed() -> None:
    breaker = _make_breaker()
    for _ in range(10):
        result = await breaker.call(_ok)
    assert result == "ok"
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_transitions_to_open_after_threshold() -> None:
    breaker = _make_breaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(ProviderError):
            await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_circuit_raises_circuit_open_error() -> None:
    breaker = _make_breaker(failure_threshold=1)
    with pytest.raises(ProviderError):
        await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await breaker.call(_ok)


@pytest.mark.asyncio
async def test_transitions_to_closed_after_successful_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker = _make_breaker(failure_threshold=1, recovery_timeout=30.0)
    with pytest.raises(ProviderError):
        await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 31.0)

    result = await breaker.call(_ok)
    assert result == "ok"
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_returns_to_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    breaker = _make_breaker(failure_threshold=1, recovery_timeout=30.0)
    with pytest.raises(ProviderError):
        await breaker.call(_fail)

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 31.0)

    with pytest.raises(ProviderError):
        await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN


@pytest.mark.asyncio
async def test_failure_counter_resets_on_success() -> None:
    breaker = _make_breaker(failure_threshold=3)
    for _ in range(2):
        with pytest.raises(ProviderError):
            await breaker.call(_fail)
    await breaker.call(_ok)
    assert breaker.state is CircuitState.CLOSED
    assert breaker._failure_count == 0


# ---------------------------------------------------------------------------
# Streaming passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_passes_through_when_closed() -> None:
    breaker = _make_breaker()

    async def _gen():
        for i in range(3):
            yield i

    collected = []
    async for item in breaker.stream(_gen):
        collected.append(item)

    assert collected == [0, 1, 2]
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_stream_records_failure_and_opens() -> None:
    breaker = _make_breaker(failure_threshold=1)

    async def _bad_gen():
        yield 1
        raise ProviderError("mid-stream", provider="test")

    with pytest.raises(ProviderError):
        async for _ in breaker.stream(_bad_gen):
            pass

    assert breaker.state is CircuitState.OPEN


@pytest.mark.asyncio
async def test_stream_raises_circuit_open_when_open() -> None:
    breaker = _make_breaker(failure_threshold=1)
    with pytest.raises(ProviderError):
        await breaker.call(_fail)

    async def _gen():
        yield 1  # pragma: no cover

    with pytest.raises(CircuitOpenError):
        async for _ in breaker.stream(_gen):
            pass
