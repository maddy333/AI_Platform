"""Router domain models: profiles, policies, context, decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from aiplatform.gateway.domain.models import ChatRequest


class RoutingStrategyName(StrEnum):
    COST = "cost"
    LATENCY = "latency"
    QUALITY = "quality"
    BALANCED = "balanced"


class UserTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PromptComplexity(StrEnum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    CODE = "code"
    CREATIVE = "creative"
    REASONING = "reasoning"


@dataclass(frozen=True)
class ModelProfile:
    """Static characteristics and pricing for a known model."""

    model_id: str
    provider: str
    context_window: int
    input_cost_per_1m: Decimal
    output_cost_per_1m: Decimal
    quality_score: float
    supports_streaming: bool = True
    supports_function_calling: bool = True
    supports_vision: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Return estimated USD cost for a request."""
        input_cost = self.input_cost_per_1m * Decimal(input_tokens) / Decimal(1_000_000)
        output_cost = self.output_cost_per_1m * Decimal(output_tokens) / Decimal(1_000_000)
        return input_cost + output_cost

    def fits_context(self, prompt_tokens: int, max_tokens: int | None = None) -> bool:
        """Return True if the request fits within the model's context window."""
        total = prompt_tokens + (max_tokens or 1024)
        return total <= self.context_window


class RoutingPolicy(BaseModel):
    """Per-tenant or per-request routing constraints."""

    allowed_models: list[str] | None = None
    denied_models: list[str] = Field(default_factory=list)
    allowed_providers: list[str] | None = None
    max_input_tokens: int | None = None
    max_cost_per_request_usd: float | None = None
    preferred_strategy: RoutingStrategyName = RoutingStrategyName.BALANCED


@dataclass(frozen=True)
class RoutingContext:
    """Everything the router needs to make a routing decision."""

    request: ChatRequest
    available_providers: list[str]
    prompt_tokens_estimate: int
    policy: RoutingPolicy = field(default_factory=RoutingPolicy)
    tenant_id: str | None = None
    user_tier: UserTier = UserTier.PRO
    strategy_override: RoutingStrategyName | None = None
    prompt_complexity: PromptComplexity = PromptComplexity.SIMPLE

    @property
    def effective_strategy(self) -> RoutingStrategyName:
        return self.strategy_override or self.policy.preferred_strategy


@dataclass(frozen=True)
class ScoredCandidate:
    """A model profile paired with its routing score and cost estimate."""

    profile: ModelProfile
    score: float
    cost_estimate_usd: float


@dataclass(frozen=True)
class RoutingDecision:
    """Ordered list of (provider, model_id) candidates produced by the router."""

    candidates: list[tuple[str, str]]
    strategy_used: RoutingStrategyName
    scores: dict[str, float]
    cost_estimates_usd: dict[str, float]
    reasoning: str

    @property
    def primary(self) -> tuple[str, str] | None:
        return self.candidates[0] if self.candidates else None
