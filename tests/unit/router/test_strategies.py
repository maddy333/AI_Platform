"""Unit tests for routing strategies: cost, latency, quality, balanced."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aiplatform.gateway.domain.models import ChatRequest, Message, MessageRole
from aiplatform.router.domain.models import (
    ModelProfile,
    PromptComplexity,
    RoutingContext,
    RoutingStrategyName,
)
from aiplatform.router.latency import LatencyTracker
from aiplatform.router.strategies.balanced import BalancedStrategy
from aiplatform.router.strategies.cost import CostStrategy
from aiplatform.router.strategies.latency import LatencyStrategy
from aiplatform.router.strategies.quality import QualityStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    model_id: str = "test",
    provider: str = "openai",
    input_cost: str = "1.00",
    output_cost: str = "4.00",
    quality: float = 0.80,
    tags: frozenset[str] = frozenset(),
) -> ModelProfile:
    return ModelProfile(
        model_id=model_id,
        provider=provider,
        context_window=128_000,
        input_cost_per_1m=Decimal(input_cost),
        output_cost_per_1m=Decimal(output_cost),
        quality_score=quality,
        tags=tags,
    )


def _context(
    model: str = "gpt-4o",
    prompt_tokens: int = 100,
    complexity: PromptComplexity = PromptComplexity.SIMPLE,
) -> RoutingContext:
    return RoutingContext(
        request=ChatRequest(
            model=model,
            messages=[Message(role=MessageRole.USER, content="hi")],
        ),
        available_providers=["openai"],
        prompt_tokens_estimate=prompt_tokens,
        prompt_complexity=complexity,
    )


# ---------------------------------------------------------------------------
# CostStrategy
# ---------------------------------------------------------------------------


class TestCostStrategy:
    def setup_method(self) -> None:
        self.strategy = CostStrategy()
        self.tracker = LatencyTracker()

    def test_name(self) -> None:
        assert self.strategy.name is RoutingStrategyName.COST

    def test_cheaper_scores_higher(self) -> None:
        cheap = _profile(model_id="cheap", input_cost="0.10", output_cost="0.30")
        expensive = _profile(model_id="expensive", input_cost="15.00", output_cost="75.00")
        ctx = _context()
        assert self.strategy.score(cheap, ctx, self.tracker) > self.strategy.score(expensive, ctx, self.tracker)

    def test_score_in_range(self) -> None:
        score = self.strategy.score(_profile(), _context(), self.tracker)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# LatencyStrategy
# ---------------------------------------------------------------------------


class TestLatencyStrategy:
    def setup_method(self) -> None:
        self.strategy = LatencyStrategy()
        self.tracker = LatencyTracker(alpha=1.0)

    def test_name(self) -> None:
        assert self.strategy.name is RoutingStrategyName.LATENCY

    def test_faster_scores_higher(self) -> None:
        fast = _profile(model_id="fast")
        slow = _profile(model_id="slow")
        self.tracker.record("fast", 100.0)
        self.tracker.record("slow", 5_000.0)
        ctx = _context()
        assert self.strategy.score(fast, ctx, self.tracker) > self.strategy.score(slow, ctx, self.tracker)

    def test_score_in_range(self) -> None:
        score = self.strategy.score(_profile(), _context(), self.tracker)
        assert 0.0 < score <= 1.0

    def test_uses_default_for_unseen_model(self) -> None:
        score = self.strategy.score(_profile(model_id="unseen"), _context(), LatencyTracker())
        assert score > 0.0


# ---------------------------------------------------------------------------
# QualityStrategy
# ---------------------------------------------------------------------------


class TestQualityStrategy:
    def setup_method(self) -> None:
        self.strategy = QualityStrategy()
        self.tracker = LatencyTracker()

    def test_name(self) -> None:
        assert self.strategy.name is RoutingStrategyName.QUALITY

    def test_higher_quality_scores_higher(self) -> None:
        low = _profile(model_id="low", quality=0.60)
        high = _profile(model_id="high", quality=0.98)
        ctx = _context()
        assert self.strategy.score(high, ctx, self.tracker) > self.strategy.score(low, ctx, self.tracker)

    def test_score_clamped_to_one(self) -> None:
        p = _profile(quality=1.0, tags=frozenset({"reasoning"}))
        ctx = _context(complexity=PromptComplexity.REASONING)
        assert self.strategy.score(p, ctx, self.tracker) <= 1.0

    def test_tag_boost_for_matching_complexity(self) -> None:
        base = _profile(quality=0.90, tags=frozenset())
        boosted = _profile(quality=0.90, tags=frozenset({"reasoning"}))
        ctx = _context(complexity=PromptComplexity.REASONING)
        assert self.strategy.score(boosted, ctx, self.tracker) > self.strategy.score(base, ctx, self.tracker)

    def test_no_boost_for_simple_prompt(self) -> None:
        base = _profile(quality=0.90, tags=frozenset())
        tagged = _profile(quality=0.90, tags=frozenset({"reasoning"}))
        ctx = _context(complexity=PromptComplexity.SIMPLE)
        assert self.strategy.score(tagged, ctx, self.tracker) == self.strategy.score(base, ctx, self.tracker)


# ---------------------------------------------------------------------------
# BalancedStrategy
# ---------------------------------------------------------------------------


class TestBalancedStrategy:
    def test_name(self) -> None:
        assert BalancedStrategy().name is RoutingStrategyName.BALANCED

    def test_score_in_range(self) -> None:
        score = BalancedStrategy().score(_profile(), _context(), LatencyTracker())
        assert 0.0 <= score <= 1.0

    def test_zero_weights_raise(self) -> None:
        with pytest.raises(ValueError):
            BalancedStrategy(cost_weight=0.0, latency_weight=0.0, quality_weight=0.0)

    def test_weights_sum_to_one(self) -> None:
        s = BalancedStrategy(cost_weight=2.0, latency_weight=2.0, quality_weight=1.0)
        assert abs(s._cw + s._lw + s._qw - 1.0) < 1e-9

    def test_quality_only_weights_rank_by_quality(self) -> None:
        strategy = BalancedStrategy(cost_weight=0.0, latency_weight=0.0, quality_weight=1.0)
        tracker = LatencyTracker()
        low = _profile(model_id="low", quality=0.50)
        high = _profile(model_id="high", quality=0.95)
        ctx = _context()
        assert strategy.score(high, ctx, tracker) > strategy.score(low, ctx, tracker)

    def test_cost_only_weights_rank_by_cost(self) -> None:
        strategy = BalancedStrategy(cost_weight=1.0, latency_weight=0.0, quality_weight=0.0)
        tracker = LatencyTracker()
        cheap = _profile(model_id="cheap", input_cost="0.10", output_cost="0.30")
        pricey = _profile(model_id="pricey", input_cost="15.00", output_cost="75.00")
        ctx = _context()
        assert strategy.score(cheap, ctx, tracker) > strategy.score(pricey, ctx, tracker)
