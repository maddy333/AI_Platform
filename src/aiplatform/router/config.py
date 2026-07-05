"""Router configuration, nested under AIP_ROUTER__ in the environment."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aiplatform.router.domain.models import RoutingStrategyName


class RouterSettings(BaseModel):
    """Routing strategy weights and EWMA tuning."""

    enabled: bool = True
    default_strategy: RoutingStrategyName = RoutingStrategyName.BALANCED

    # Balanced strategy weights
    cost_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    latency_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    quality_weight: float = Field(default=0.30, ge=0.0, le=1.0)

    # EWMA smoothing factor for latency tracker (higher = faster adaptation)
    latency_alpha: float = Field(default=0.2, gt=0.0, le=1.0)

    # Assumed output tokens when max_tokens is not set by the caller
    default_output_tokens: int = Field(default=512, ge=1)
