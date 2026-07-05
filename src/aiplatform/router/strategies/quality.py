"""Quality-optimised routing strategy — maximises benchmark quality score."""

from __future__ import annotations

from aiplatform.router.domain.models import (
    ModelProfile,
    PromptComplexity,
    RoutingContext,
    RoutingStrategyName,
)
from aiplatform.router.latency import LatencyTracker

_COMPLEXITY_BOOST: dict[PromptComplexity, frozenset[str]] = {
    PromptComplexity.REASONING: frozenset({"reasoning", "math", "science"}),
    PromptComplexity.CODE: frozenset({"code", "reasoning"}),
}
_BOOST_AMOUNT = 0.03


class QualityStrategy:
    """Score = quality_score with a small tag-based boost for complex prompts."""

    @property
    def name(self) -> RoutingStrategyName:
        return RoutingStrategyName.QUALITY

    def score(
        self,
        profile: ModelProfile,
        context: RoutingContext,
        latency_tracker: LatencyTracker,
    ) -> float:
        base = profile.quality_score
        required_tags = _COMPLEXITY_BOOST.get(context.prompt_complexity, frozenset())
        boost = _BOOST_AMOUNT if required_tags & profile.tags else 0.0
        return min(1.0, base + boost)
