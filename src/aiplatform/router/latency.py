"""EWMA latency tracker per model.

Records observed response times and produces smoothed estimates used by the
latency routing strategy. All state is in-process; a Redis upgrade is planned
for the persistence milestone to share estimates across replicas.
"""

from __future__ import annotations

import threading

_DEFAULT_LATENCY_MS = 1_000.0
_DEFAULT_ALPHA = 0.2


class LatencyTracker:
    """Thread-safe exponential weighted moving average latency per model."""

    def __init__(self, alpha: float = _DEFAULT_ALPHA) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1]; got {alpha}")
        self._alpha = alpha
        self._estimates: dict[str, float] = {}
        self._lock = threading.Lock()

    def record(self, model_id: str, latency_ms: float) -> None:
        """Update the EWMA estimate for model_id with a new observation."""
        with self._lock:
            current = self._estimates.get(model_id, latency_ms)
            self._estimates[model_id] = (
                self._alpha * latency_ms + (1.0 - self._alpha) * current
            )

    def estimate(self, model_id: str) -> float:
        """Return the current EWMA estimate in ms; defaults to 1 000 ms if unseen."""
        with self._lock:
            return self._estimates.get(model_id, _DEFAULT_LATENCY_MS)

    def all_estimates(self) -> dict[str, float]:
        with self._lock:
            return dict(self._estimates)

    def reset(self, model_id: str) -> None:
        with self._lock:
            self._estimates.pop(model_id, None)
