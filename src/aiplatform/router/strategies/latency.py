"""Latency-optimised routing strategy — minimises EWMA response time."""

from __future__ import annotations

from aiplatform.router.domain.models import ModelProfile, RoutingContext, RoutingStrategyName
from aiplatform.router.latency import LatencyTracker

_MAX_LATENCY_MS = 10_000.0


class LatencyStrategy:
    """Score = 1 / (1 + latency_s); faster models score higher."""

    @property
    def name(self) -> RoutingStrategyName:
        return RoutingStrategyName.LATENCY

    def score(
        self,
        profile: ModelProfile,
        context: RoutingContext,
        latency_tracker: LatencyTracker,
    ) -> float:
        latency_ms = min(latency_tracker.estimate(profile.model_id), _MAX_LATENCY_MS)
        latency_s = latency_ms / 1_000.0
        return 1.0 / (1.0 + latency_s)
