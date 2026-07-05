"""Cost-optimised routing strategy — minimises estimated USD per request."""

from __future__ import annotations

from aiplatform.router.domain.models import ModelProfile, RoutingContext, RoutingStrategyName
from aiplatform.router.latency import LatencyTracker

_DEFAULT_OUTPUT_TOKENS = 512


class CostStrategy:
    """Score = 1 / (1 + estimated_cost_usd); cheaper models score higher."""

    @property
    def name(self) -> RoutingStrategyName:
        return RoutingStrategyName.COST

    def score(
        self,
        profile: ModelProfile,
        context: RoutingContext,
        latency_tracker: LatencyTracker,
    ) -> float:
        output_tokens = context.request.max_tokens or _DEFAULT_OUTPUT_TOKENS
        cost_usd = float(profile.estimate_cost(context.prompt_tokens_estimate, output_tokens))
        return 1.0 / (1.0 + cost_usd)
