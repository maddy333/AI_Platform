"""Unit tests for RouterService — policy, strategy selection, virtual aliases."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aiplatform.gateway.domain.models import ChatRequest, Message, MessageRole
from aiplatform.router.config import RouterSettings
from aiplatform.router.domain.errors import NoEligibleModelError
from aiplatform.router.domain.models import (
    ModelProfile,
    RoutingPolicy,
    RoutingStrategyName,
)
from aiplatform.router.service import RouterService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(model: str = "gpt-4o") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role=MessageRole.USER, content="hello")],
    )


def _service(**kwargs) -> RouterService:  # type: ignore[no-untyped-def]
    return RouterService(RouterSettings(**kwargs))


# ---------------------------------------------------------------------------
# select() — catalog models
# ---------------------------------------------------------------------------


def test_select_returns_decision_for_catalog_model() -> None:
    svc = _service()
    ctx = svc.build_context(_req("gpt-4o"), available_providers=["openai"])
    decision = svc.select(ctx)
    assert decision.primary is not None
    provider, model_id = decision.primary
    assert provider == "openai"
    assert model_id == "gpt-4o"


def test_select_raises_when_provider_not_available() -> None:
    svc = _service()
    ctx = svc.build_context(_req("gpt-4o"), available_providers=[])
    with pytest.raises(NoEligibleModelError):
        svc.select(ctx)


def test_select_raises_for_unknown_model_with_no_providers() -> None:
    svc = _service()
    ctx = svc.build_context(_req("unknown-model-xyz"), available_providers=["openai"])
    with pytest.raises(NoEligibleModelError):
        svc.select(ctx)


# ---------------------------------------------------------------------------
# select() — virtual aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alias", ["smart", "fast", "cheap", "balanced"])
def test_select_resolves_virtual_alias(alias: str) -> None:
    svc = _service()
    providers = ["openai", "anthropic", "gemini"]
    ctx = svc.build_context(_req(alias), available_providers=providers)
    decision = svc.select(ctx)
    assert len(decision.candidates) > 0
    # Resolved model must not be the alias itself
    for _, model_id in decision.candidates:
        assert model_id != alias


def test_smart_alias_uses_quality_strategy() -> None:
    svc = _service()
    ctx = svc.build_context(_req("smart"), available_providers=["openai", "anthropic"])
    decision = svc.select(ctx)
    assert decision.strategy_used is RoutingStrategyName.QUALITY


def test_fast_alias_uses_latency_strategy() -> None:
    svc = _service()
    ctx = svc.build_context(_req("fast"), available_providers=["openai"])
    decision = svc.select(ctx)
    assert decision.strategy_used is RoutingStrategyName.LATENCY


def test_cheap_alias_uses_cost_strategy() -> None:
    svc = _service()
    ctx = svc.build_context(_req("cheap"), available_providers=["openai"])
    decision = svc.select(ctx)
    assert decision.strategy_used is RoutingStrategyName.COST


# ---------------------------------------------------------------------------
# Policy filtering
# ---------------------------------------------------------------------------


def test_policy_denied_model_is_excluded() -> None:
    svc = _service()
    policy = RoutingPolicy(denied_models=["gpt-4o"])
    ctx = svc.build_context(_req("smart"), available_providers=["openai"], policy=policy)
    decision = svc.select(ctx)
    for _, model_id in decision.candidates:
        assert model_id != "gpt-4o"


def test_policy_allowed_models_restricts_candidates() -> None:
    svc = _service()
    policy = RoutingPolicy(allowed_models=["gpt-4o-mini"])
    ctx = svc.build_context(_req("balanced"), available_providers=["openai"], policy=policy)
    decision = svc.select(ctx)
    assert all(mid == "gpt-4o-mini" for _, mid in decision.candidates)


def test_policy_cost_ceiling_excludes_expensive_models() -> None:
    svc = _service()
    # Cap at $0.0001 — only the cheapest models survive
    policy = RoutingPolicy(max_cost_per_request_usd=0.0001)
    ctx = svc.build_context(
        _req("cheap"),
        available_providers=["openai", "anthropic", "gemini"],
        policy=policy,
    )
    decision = svc.select(ctx)
    # All surviving candidates must be within budget
    for _, model_id in decision.candidates:
        assert decision.cost_estimates_usd[model_id] <= 0.0001


def test_policy_all_models_denied_raises() -> None:
    svc = _service()
    policy = RoutingPolicy(denied_models=["gpt-4o"])
    ctx = svc.build_context(_req("gpt-4o"), available_providers=["openai"], policy=policy)
    with pytest.raises(NoEligibleModelError):
        svc.select(ctx)


def test_policy_allowed_providers_restricts_candidates() -> None:
    svc = _service()
    policy = RoutingPolicy(allowed_providers=["anthropic"])
    ctx = svc.build_context(
        _req("balanced"),
        available_providers=["openai", "anthropic"],
        policy=policy,
    )
    decision = svc.select(ctx)
    for provider, _ in decision.candidates:
        assert provider == "anthropic"


# ---------------------------------------------------------------------------
# record_latency
# ---------------------------------------------------------------------------


def test_record_latency_does_not_raise() -> None:
    svc = _service()
    svc.record_latency("gpt-4o", 350.0)


def test_latency_affects_subsequent_routing() -> None:
    svc = _service()
    # Seed fast latency for gpt-4o-mini so latency strategy prefers it
    svc.record_latency("gpt-4o-mini", 50.0)
    svc.record_latency("gpt-4o", 4_000.0)
    ctx = svc.build_context(_req("fast"), available_providers=["openai"])
    decision = svc.select(ctx)
    # First candidate should be the fast model
    assert decision.primary is not None
    _, top_model = decision.primary
    assert top_model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Decision structure
# ---------------------------------------------------------------------------


def test_decision_scores_populated() -> None:
    svc = _service()
    ctx = svc.build_context(_req("balanced"), available_providers=["openai", "anthropic"])
    decision = svc.select(ctx)
    assert len(decision.scores) > 0
    for score in decision.scores.values():
        assert 0.0 <= score <= 1.0


def test_decision_cost_estimates_populated() -> None:
    svc = _service()
    ctx = svc.build_context(_req("balanced"), available_providers=["openai"])
    decision = svc.select(ctx)
    assert len(decision.cost_estimates_usd) > 0
    for cost in decision.cost_estimates_usd.values():
        assert cost >= 0.0
