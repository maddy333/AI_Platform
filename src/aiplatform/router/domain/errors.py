"""Router-specific exception hierarchy."""

from __future__ import annotations

from aiplatform.core.errors import PlatformError


class RouterError(PlatformError):
    """Base for all router errors."""

    error_code = "router_error"
    status_code = 500


class NoEligibleModelError(RouterError):
    """No model passed all policy and availability filters."""

    error_code = "no_eligible_model"
    status_code = 503


class PolicyViolationError(RouterError):
    """Request violates tenant routing policy (cost ceiling, denied model, etc.)."""

    error_code = "policy_violation"
    status_code = 400


class VirtualAliasNotResolvableError(RouterError):
    """A virtual alias (smart/fast/cheap) could not be resolved to any live model."""

    error_code = "virtual_alias_not_resolvable"
    status_code = 503
