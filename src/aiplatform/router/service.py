"""RouterService — policy enforcement, scoring, and candidate ranking."""

from __future__ import annotations

import structlog

from aiplatform.gateway.accounting import estimate_prompt_tokens
from aiplatform.gateway.domain.models import ChatRequest
from aiplatform.router.catalog import MODEL_CATALOG, is_virtual_alias, profiles_for_provider
from aiplatform.router.classifier import classify
from aiplatform.router.config import RouterSettings
from aiplatform.router.domain.errors import NoEligibleModelError
from aiplatform.router.domain.models import (
    ModelProfile,
    RoutingContext,
    RoutingDecision,
    RoutingPolicy,
    RoutingStrategyName,
    ScoredCandidate,
    UserTier,
)
from aiplatform.router.latency import LatencyTracker
from aiplatform.router.strategies.balanced import BalancedStrategy
from aiplatform.router.strategies.base import RoutingStrategy
from aiplatform.router.strategies.cost import CostStrategy
from aiplatform.router.strategies.latency import LatencyStrategy
from aiplatform.router.strategies.quality import QualityStrategy

logger = structlog.stdlib.get_logger(__name__)

_ALIAS_STRATEGY: dict[str, RoutingStrategyName] = {
    "smart": RoutingStrategyName.QUALITY,
    "fast": RoutingStrategyName.LATENCY,
    "cheap": RoutingStrategyName.COST,
    "balanced": RoutingStrategyName.BALANCED,
}


class RouterService:
    """Select the best ordered list of (provider, model_id) for a request."""

    def __init__(self, settings: RouterSettings | None = None) -> None:
        cfg = settings or RouterSettings()
        self._default_strategy = cfg.default_strategy
        self._default_output_tokens = cfg.default_output_tokens
        self._latency_tracker = LatencyTracker(alpha=cfg.latency_alpha)
        self._strategies: dict[RoutingStrategyName, RoutingStrategy] = {
            RoutingStrategyName.COST: CostStrategy(),
            RoutingStrategyName.LATENCY: LatencyStrategy(),
            RoutingStrategyName.QUALITY: QualityStrategy(),
            RoutingStrategyName.BALANCED: BalancedStrategy(
                cost_weight=cfg.cost_weight,
                latency_weight=cfg.latency_weight,
                quality_weight=cfg.quality_weight,
            ),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_context(
        self,
        request: ChatRequest,
        available_providers: list[str],
        policy: RoutingPolicy | None = None,
        tenant_id: str | None = None,
        user_tier: UserTier = UserTier.PRO,
    ) -> RoutingContext:
        """Construct a RoutingContext, including token estimation and classification."""
        prompt_tokens = estimate_prompt_tokens(request.messages, model=request.model)
        complexity = classify(request.messages, prompt_tokens)
        alias_strategy: RoutingStrategyName | None = (
            _ALIAS_STRATEGY.get(request.model) if is_virtual_alias(request.model) else None
        )
        return RoutingContext(
            request=request,
            available_providers=available_providers,
            prompt_tokens_estimate=prompt_tokens,
            policy=policy or RoutingPolicy(),
            tenant_id=tenant_id,
            user_tier=user_tier,
            strategy_override=alias_strategy,
            prompt_complexity=complexity,
        )

    def select(self, context: RoutingContext) -> RoutingDecision:
        """Return an ordered list of (provider, model_id) routing candidates."""
        candidates = self._gather_candidates(context)
        if not candidates:
            raise NoEligibleModelError(
                f"No eligible model for '{context.request.model}' "
                f"across providers {context.available_providers}",
            )

        strategy = self._strategies[context.effective_strategy]
        scored = self._score_and_sort(candidates, context, strategy)
        ordered = [(c.profile.provider, c.profile.model_id) for c in scored]

        logger.debug(
            "routing_decision",
            model=context.request.model,
            strategy=strategy.name,
            top=ordered[0] if ordered else None,
            count=len(ordered),
        )
        return RoutingDecision(
            candidates=ordered,
            strategy_used=strategy.name,
            scores={c.profile.model_id: c.score for c in scored},
            cost_estimates_usd={c.profile.model_id: c.cost_estimate_usd for c in scored},
            reasoning=f"strategy={strategy.name}, candidates={len(ordered)}",
        )

    def record_latency(self, model_id: str, latency_ms: float) -> None:
        """Feed an observed response time back into the EWMA tracker."""
        self._latency_tracker.record(model_id, latency_ms)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _gather_candidates(self, context: RoutingContext) -> list[ModelProfile]:
        model_id = context.request.model
        if is_virtual_alias(model_id):
            profiles: list[ModelProfile] = []
            for provider in context.available_providers:
                profiles.extend(profiles_for_provider(provider))
        elif model_id in MODEL_CATALOG:
            profile = MODEL_CATALOG[model_id]
            profiles = [profile] if profile.provider in context.available_providers else []
        else:
            return []  # unknown model — gateway handles it without router ordering
        return self._apply_policy(profiles, context)

    def _apply_policy(
        self, profiles: list[ModelProfile], context: RoutingContext
    ) -> list[ModelProfile]:
        policy = context.policy
        output_tokens = context.request.max_tokens or self._default_output_tokens
        result = []
        for p in profiles:
            if policy.allowed_models is not None and p.model_id not in policy.allowed_models:
                continue
            if p.model_id in policy.denied_models:
                continue
            if policy.allowed_providers is not None and p.provider not in policy.allowed_providers:
                continue
            if not p.fits_context(context.prompt_tokens_estimate, context.request.max_tokens):
                continue
            if policy.max_input_tokens and context.prompt_tokens_estimate > policy.max_input_tokens:
                continue
            if policy.max_cost_per_request_usd is not None:
                cost = float(p.estimate_cost(context.prompt_tokens_estimate, output_tokens))
                if cost > policy.max_cost_per_request_usd:
                    continue
            if context.request.tools and not p.supports_function_calling:
                continue
            result.append(p)
        return result

    def _score_and_sort(
        self,
        profiles: list[ModelProfile],
        context: RoutingContext,
        strategy: RoutingStrategy,
    ) -> list[ScoredCandidate]:
        output_tokens = context.request.max_tokens or self._default_output_tokens
        scored = [
            ScoredCandidate(
                profile=p,
                score=strategy.score(p, context, self._latency_tracker),
                cost_estimate_usd=float(
                    p.estimate_cost(context.prompt_tokens_estimate, output_tokens)
                ),
            )
            for p in profiles
        ]
        return sorted(scored, key=lambda c: c.score, reverse=True)
