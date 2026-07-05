"""Redis health check registered with the platform HealthRegistry."""

from __future__ import annotations

from aiplatform.cache.client import get_redis


async def check_redis() -> None:
    """Send a PING to Redis.

    Raises on any connection failure so the health registry can mark the
    service as not-ready.
    """
    client = get_redis()
    await client.ping()
