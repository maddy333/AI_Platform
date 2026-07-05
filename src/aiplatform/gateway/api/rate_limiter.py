"""In-process token-bucket rate limiter (per API key / user identifier).

Single-process only. Multi-replica deployments replace the in-memory
buckets with Redis INCR+EXPIRE atomics — planned for the persistence milestone.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from aiplatform.gateway.domain.errors import GatewayRateLimitError


@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class TokenBucketRateLimiter:
    """Per-key token-bucket: ``rpm`` requests/minute, burst = rpm."""

    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._refill_rate = rpm / 60.0
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(tokens=float(rpm)))

    def check(self, key: str) -> None:
        """Consume one token; raise ``GatewayRateLimitError`` if exhausted."""
        bucket = self._buckets[key]
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(self._rpm, bucket.tokens + elapsed * self._refill_rate)
        bucket.last_refill = now
        if bucket.tokens < 1:
            raise GatewayRateLimitError(
                f"Rate limit exceeded: {self._rpm} requests/minute",
                context={"key": key, "rpm_limit": self._rpm},
            )
        bucket.tokens -= 1
