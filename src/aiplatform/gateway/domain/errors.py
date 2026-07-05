"""Gateway-specific domain errors."""

from fastapi import status

from aiplatform.core.errors import PlatformError


class ProviderError(PlatformError):
    """An LLM provider returned an error or behaved unexpectedly."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "provider_error"
    title = "Provider Error"


class ProviderRateLimitError(ProviderError):
    """The provider is rate-limiting this client; caller should back off."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "provider_rate_limit"
    title = "Provider Rate Limit"


class ProviderAuthError(ProviderError):
    """The provider rejected our credentials; requires operator action."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "provider_auth_error"
    title = "Provider Authentication Error"


class ProviderContextLengthError(ProviderError):
    """The request exceeds the model's context window."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "context_length_exceeded"
    title = "Context Length Exceeded"


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "provider_timeout"
    title = "Provider Timeout"


class CircuitOpenError(PlatformError):
    """The circuit breaker is open; requests to this provider are blocked."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "circuit_open"
    title = "Provider Circuit Open"


class NoHealthyProviderError(PlatformError):
    """No healthy provider is available for the requested model."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "no_healthy_provider"
    title = "No Healthy Provider"


class ModelNotFoundError(PlatformError):
    """The requested model is not registered on any configured provider."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "model_not_found"
    title = "Model Not Found"


class GatewayRateLimitError(PlatformError):
    """The platform-level rate limit for this key/tenant has been reached."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"
    title = "Rate Limit Exceeded"
