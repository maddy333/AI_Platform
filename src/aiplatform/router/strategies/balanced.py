"""Balanced routing strategy — weighted blend of cost, latency, and quality."""

from __future__ import annotations

from aiplatform.router.domain.models import ModelProfile, RoutingContext, RoutingStrategyName
from aiplatform.router.latency import LatencyTracker
from aiplatform.router.strategies.cost import CostStrategy
from aiplatform.router.strategies.latency import LatencyStrategy
from aiplatform.router.strategies.quality import QualityStrategy


class BalancedStrategy:
    """Linearly combines normalised cost, latency, and quality scores."""

    def __init__(
        self,
        cost_weight: float = 0.35,
        latency_weight: float = 0.35,
        quality_weight: float = 0.30,
    ) -> None:
        total = cost_weight + latency_weight + quality_weight
        if total <= 0:
            raise ValueError("Strategy weights must sum to a positive number.")
        self._cw = cost_weight / total
        self._lw = latency_weight / total
        self._qw = quality_weight / total
        self._cost = CostStrategy()
        self._latency = LatencyStrategy()
        self._quality = QualityStrategy()

    @property
    def name(self) -> RoutingStrategyName:
        return RoutingStrategyName.BALANCED

    def score(
        self,
        profile: ModelProfile,
        context: RoutingContext,
        latency_tracker: LatencyTracker,
    ) -> float:
        c = self._cost.score(profile, context, latency_tracker)
        lat = self._latency.score(profile, context, latency_tracker)
        q = self._quality.score(profile, context, latency_tracker)
        return self._cw * c + self._lw * lat + self._qw * q
