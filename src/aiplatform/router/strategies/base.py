"""RoutingStrategy structural Protocol and shared scoring utilities."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aiplatform.router.domain.models import ModelProfile, RoutingContext, RoutingStrategyName
from aiplatform.router.latency import LatencyTracker


@runtime_checkable
class RoutingStrategy(Protocol):
    """Score a single model profile given the current routing context."""

    @property
    def name(self) -> RoutingStrategyName: ...

    def score(
        self,
        profile: ModelProfile,
        context: RoutingContext,
        latency_tracker: LatencyTracker,
    ) -> float:
        """Return a score in [0, 1]; higher is better for this strategy."""
        ...


def normalise(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalise a dict of raw scores to [0, 1]."""
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    span = hi - lo
    if span == 0.0:
        return {k: 1.0 for k in values}
    return {k: (v - lo) / span for k, v in values.items()}
