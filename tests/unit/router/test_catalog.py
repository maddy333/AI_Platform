"""Unit tests for the model catalog and ModelProfile helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aiplatform.router.catalog import (
    MODEL_CATALOG,
    VIRTUAL_ALIASES,
    get_profile,
    is_virtual_alias,
    profiles_for_provider,
)


# ---------------------------------------------------------------------------
# Catalog completeness
# ---------------------------------------------------------------------------


def test_catalog_is_non_empty() -> None:
    assert len(MODEL_CATALOG) > 0


def test_all_catalog_entries_have_valid_quality_scores() -> None:
    for model_id, profile in MODEL_CATALOG.items():
        assert 0.0 <= profile.quality_score <= 1.0, f"{model_id} quality_score out of range"


def test_all_catalog_entries_have_positive_context_windows() -> None:
    for model_id, profile in MODEL_CATALOG.items():
        assert profile.context_window > 0, f"{model_id} has zero context_window"


def test_all_catalog_entries_have_positive_costs() -> None:
    for model_id, profile in MODEL_CATALOG.items():
        assert profile.input_cost_per_1m > Decimal("0"), f"{model_id} has zero input cost"
        assert profile.output_cost_per_1m > Decimal("0"), f"{model_id} has zero output cost"


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


def test_get_profile_known_model() -> None:
    profile = get_profile("gpt-4o")
    assert profile is not None
    assert profile.model_id == "gpt-4o"
    assert profile.provider == "openai"


def test_get_profile_unknown_model_returns_none() -> None:
    assert get_profile("no-such-model-xyz") is None


# ---------------------------------------------------------------------------
# profiles_for_provider
# ---------------------------------------------------------------------------


def test_profiles_for_openai() -> None:
    profiles = profiles_for_provider("openai")
    assert len(profiles) > 0
    assert all(p.provider == "openai" for p in profiles)


def test_profiles_for_anthropic() -> None:
    profiles = profiles_for_provider("anthropic")
    assert len(profiles) > 0
    assert all(p.provider == "anthropic" for p in profiles)


def test_profiles_for_unknown_provider_returns_empty() -> None:
    assert profiles_for_provider("no-such-provider") == []


# ---------------------------------------------------------------------------
# is_virtual_alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alias", ["smart", "fast", "cheap", "balanced"])
def test_is_virtual_alias_for_all_aliases(alias: str) -> None:
    assert is_virtual_alias(alias) is True


def test_is_virtual_alias_false_for_real_model_id() -> None:
    assert is_virtual_alias("gpt-4o") is False


def test_virtual_aliases_set_matches_function() -> None:
    for alias in VIRTUAL_ALIASES:
        assert is_virtual_alias(alias)


# ---------------------------------------------------------------------------
# ModelProfile.estimate_cost
# ---------------------------------------------------------------------------


def test_estimate_cost_positive_for_nonzero_tokens() -> None:
    profile = get_profile("gpt-4o")
    assert profile is not None
    cost = profile.estimate_cost(input_tokens=1_000, output_tokens=200)
    assert isinstance(cost, Decimal)
    assert cost > Decimal("0")


def test_estimate_cost_scales_with_tokens() -> None:
    profile = get_profile("gpt-4o")
    assert profile is not None
    small = profile.estimate_cost(100, 50)
    large = profile.estimate_cost(10_000, 5_000)
    assert large > small


def test_estimate_cost_zero_tokens_is_zero() -> None:
    profile = get_profile("gpt-4o-mini")
    assert profile is not None
    assert profile.estimate_cost(0, 0) == Decimal("0")


# ---------------------------------------------------------------------------
# ModelProfile.fits_context
# ---------------------------------------------------------------------------


def test_fits_context_within_window() -> None:
    profile = get_profile("gpt-4o")
    assert profile is not None
    assert profile.fits_context(prompt_tokens=1_000, max_tokens=500) is True


def test_fits_context_exceeds_window() -> None:
    profile = get_profile("gpt-4o")
    assert profile is not None
    assert profile.fits_context(prompt_tokens=127_000, max_tokens=5_000) is False


def test_fits_context_uses_default_when_max_tokens_none() -> None:
    profile = get_profile("gpt-4o-mini")
    assert profile is not None
    assert profile.fits_context(prompt_tokens=100, max_tokens=None) is True
