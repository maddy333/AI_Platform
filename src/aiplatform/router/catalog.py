"""Static model catalog: context windows, pricing, and quality scores.

Prices are in USD per 1M tokens (industry-standard unit as of 2026).
Quality scores are a normalised blend of public benchmark performance.
Update this catalog when providers publish new models or reprice existing ones.
"""

from __future__ import annotations

from decimal import Decimal

from aiplatform.router.domain.models import ModelProfile

_D = Decimal

MODEL_CATALOG: dict[str, ModelProfile] = {
    # -------------------------------------------------------------------------
    # OpenAI
    # -------------------------------------------------------------------------
    "gpt-4o": ModelProfile(
        model_id="gpt-4o",
        provider="openai",
        context_window=128_000,
        input_cost_per_1m=_D("2.50"),
        output_cost_per_1m=_D("10.00"),
        quality_score=0.93,
        supports_vision=True,
        tags=frozenset({"multimodal", "reasoning", "code"}),
    ),
    "gpt-4o-mini": ModelProfile(
        model_id="gpt-4o-mini",
        provider="openai",
        context_window=128_000,
        input_cost_per_1m=_D("0.15"),
        output_cost_per_1m=_D("0.60"),
        quality_score=0.75,
        tags=frozenset({"fast", "cheap"}),
    ),
    "o1": ModelProfile(
        model_id="o1",
        provider="openai",
        context_window=200_000,
        input_cost_per_1m=_D("15.00"),
        output_cost_per_1m=_D("60.00"),
        quality_score=0.97,
        supports_function_calling=False,
        tags=frozenset({"reasoning", "math", "science"}),
    ),
    "o1-mini": ModelProfile(
        model_id="o1-mini",
        provider="openai",
        context_window=128_000,
        input_cost_per_1m=_D("3.00"),
        output_cost_per_1m=_D("12.00"),
        quality_score=0.88,
        supports_function_calling=False,
        tags=frozenset({"reasoning", "code"}),
    ),
    "o3-mini": ModelProfile(
        model_id="o3-mini",
        provider="openai",
        context_window=200_000,
        input_cost_per_1m=_D("1.10"),
        output_cost_per_1m=_D("4.40"),
        quality_score=0.91,
        tags=frozenset({"reasoning", "code", "fast"}),
    ),
    # -------------------------------------------------------------------------
    # Anthropic
    # -------------------------------------------------------------------------
    "claude-opus-4-8": ModelProfile(
        model_id="claude-opus-4-8",
        provider="anthropic",
        context_window=200_000,
        input_cost_per_1m=_D("15.00"),
        output_cost_per_1m=_D("75.00"),
        quality_score=0.98,
        supports_vision=True,
        tags=frozenset({"reasoning", "code", "analysis", "writing"}),
    ),
    "claude-sonnet-4-6": ModelProfile(
        model_id="claude-sonnet-4-6",
        provider="anthropic",
        context_window=200_000,
        input_cost_per_1m=_D("3.00"),
        output_cost_per_1m=_D("15.00"),
        quality_score=0.95,
        supports_vision=True,
        tags=frozenset({"code", "analysis", "reasoning"}),
    ),
    "claude-3-5-sonnet-20241022": ModelProfile(
        model_id="claude-3-5-sonnet-20241022",
        provider="anthropic",
        context_window=200_000,
        input_cost_per_1m=_D("3.00"),
        output_cost_per_1m=_D("15.00"),
        quality_score=0.92,
        supports_vision=True,
        tags=frozenset({"code", "analysis"}),
    ),
    "claude-haiku-4-5-20251001": ModelProfile(
        model_id="claude-haiku-4-5-20251001",
        provider="anthropic",
        context_window=200_000,
        input_cost_per_1m=_D("0.80"),
        output_cost_per_1m=_D("4.00"),
        quality_score=0.78,
        tags=frozenset({"fast", "cheap"}),
    ),
    "claude-3-5-haiku-20241022": ModelProfile(
        model_id="claude-3-5-haiku-20241022",
        provider="anthropic",
        context_window=200_000,
        input_cost_per_1m=_D("0.80"),
        output_cost_per_1m=_D("4.00"),
        quality_score=0.76,
        tags=frozenset({"fast", "cheap"}),
    ),
    # -------------------------------------------------------------------------
    # Google Gemini
    # -------------------------------------------------------------------------
    "gemini-2.5-pro": ModelProfile(
        model_id="gemini-2.5-pro",
        provider="gemini",
        context_window=1_048_576,
        input_cost_per_1m=_D("1.25"),
        output_cost_per_1m=_D("10.00"),
        quality_score=0.96,
        supports_vision=True,
        tags=frozenset({"long-context", "reasoning", "multimodal"}),
    ),
    "gemini-2.0-flash": ModelProfile(
        model_id="gemini-2.0-flash",
        provider="gemini",
        context_window=1_048_576,
        input_cost_per_1m=_D("0.10"),
        output_cost_per_1m=_D("0.40"),
        quality_score=0.82,
        supports_vision=True,
        tags=frozenset({"fast", "cheap", "long-context"}),
    ),
    "gemini-2.0-flash-lite": ModelProfile(
        model_id="gemini-2.0-flash-lite",
        provider="gemini",
        context_window=1_048_576,
        input_cost_per_1m=_D("0.075"),
        output_cost_per_1m=_D("0.30"),
        quality_score=0.70,
        tags=frozenset({"fast", "cheap", "long-context"}),
    ),
    "gemini-1.5-pro": ModelProfile(
        model_id="gemini-1.5-pro",
        provider="gemini",
        context_window=2_097_152,
        input_cost_per_1m=_D("3.50"),
        output_cost_per_1m=_D("10.50"),
        quality_score=0.90,
        supports_vision=True,
        tags=frozenset({"long-context", "multimodal"}),
    ),
}

VIRTUAL_ALIASES: frozenset[str] = frozenset({"smart", "fast", "cheap", "balanced"})


def get_profile(model_id: str) -> ModelProfile | None:
    """Return the profile for a known model ID, or None if not in the catalog."""
    return MODEL_CATALOG.get(model_id)


def profiles_for_provider(provider: str) -> list[ModelProfile]:
    """Return all catalog entries whose provider matches."""
    return [p for p in MODEL_CATALOG.values() if p.provider == provider]


def is_virtual_alias(model_id: str) -> bool:
    return model_id in VIRTUAL_ALIASES
