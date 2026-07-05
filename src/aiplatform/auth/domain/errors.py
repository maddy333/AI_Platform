"""Auth domain error hierarchy."""

from __future__ import annotations

from aiplatform.core.errors import PlatformError


class AuthError(PlatformError):
    error_code = "auth_error"
    status_code = 401


class InvalidCredentialsError(AuthError):
    error_code = "invalid_credentials"
    status_code = 401


class TokenExpiredError(AuthError):
    error_code = "token_expired"
    status_code = 401


class TokenInvalidError(AuthError):
    error_code = "token_invalid"
    status_code = 401


class PermissionDeniedError(AuthError):
    error_code = "permission_denied"
    status_code = 403


class TenantNotFoundError(AuthError):
    error_code = "tenant_not_found"
    status_code = 404


class UserNotFoundError(AuthError):
    error_code = "user_not_found"
    status_code = 404


class UserAlreadyExistsError(AuthError):
    error_code = "user_already_exists"
    status_code = 409


class APIKeyNotFoundError(AuthError):
    error_code = "api_key_not_found"
    status_code = 404


class APIKeyRevokedError(AuthError):
    error_code = "api_key_revoked"
    status_code = 401
