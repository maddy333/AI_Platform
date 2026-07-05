"""Async Redis client singleton.

The client is initialised once during the application lifespan and made
available via ``get_redis()``.  All callers receive the same connection pool
so connections are reused efficiently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import redis.asyncio as aioredis
from redis.asyncio import Redis

if TYPE_CHECKING:
    from aiplatform.core.config import RedisSettings

_redis: Redis | None = None  # type: ignore[type-arg]


def init_redis(settings: RedisSettings) -> Redis:  # type: ignore[type-arg]
    """Create the Redis client singleton.  No-op if already initialised."""
    global _redis  # noqa: PLW0603
    if _redis is not None:
        return _redis

    _redis = aioredis.from_url(
        settings.url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.max_connections,
        socket_connect_timeout=settings.connect_timeout,
        socket_timeout=settings.socket_timeout,
        health_check_interval=30,
    )
    return _redis


async def close_redis() -> None:
    """Close the Redis connection pool.  Called at application shutdown."""
    global _redis  # noqa: PLW0603
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:  # type: ignore[type-arg]
    """Return the Redis client singleton.

    Raises ``RuntimeError`` if ``init_redis()`` has not been called yet.
    """
    if _redis is None:
        msg = "Redis client has not been initialised. Call init_redis() first."
        raise RuntimeError(msg)
    return _redis
