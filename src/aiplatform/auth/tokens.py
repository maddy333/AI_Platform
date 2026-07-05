"""JWT access and refresh token creation and verification.

Uses PyJWT with HS256.  RS256 is the recommended upgrade path for multi-service
deployments where the gateway needs to verify tokens without sharing a secret.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from aiplatform.auth.domain.errors import TokenExpiredError, TokenInvalidError
from aiplatform.auth.domain.models import Role, TokenClaims

if TYPE_CHECKING:
    from aiplatform.auth.config import AuthSettings

_ACCESS = "access"
_REFRESH = "refresh"


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    roles: frozenset[Role],
    settings: AuthSettings,
    extra: dict[str, str] | None = None,
) -> str:
    """Return a signed JWT access token."""
    now = _now()
    payload: dict[str, object] = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "roles": [r.value for r in roles],
        "jti": str(uuid.uuid4()),
        "type": _ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    roles: frozenset[Role],
    settings: AuthSettings,
) -> str:
    """Return a signed JWT refresh token."""
    now = _now()
    payload: dict[str, object] = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "roles": [r.value for r in roles],
        "jti": str(uuid.uuid4()),
        "type": _REFRESH,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)


def decode_token(raw: str, settings: AuthSettings) -> TokenClaims:
    """Decode and validate *raw*; raise domain errors on any failure."""
    try:
        payload = jwt.decode(
            raw,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired.") from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError(f"Invalid token: {exc}") from exc

    try:
        return TokenClaims(
            sub=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
            roles=frozenset(Role(r) for r in payload.get("roles", [])),
            jti=uuid.UUID(payload["jti"]),
            token_type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        )
    except (KeyError, ValueError) as exc:
        raise TokenInvalidError(f"Malformed token payload: {exc}") from exc


def decode_access_token(raw: str, settings: AuthSettings) -> TokenClaims:
    """Decode *raw* and enforce that it is an access token."""
    claims = decode_token(raw, settings)
    if claims.token_type != _ACCESS:
        raise TokenInvalidError("Expected an access token.")
    return claims


def decode_refresh_token(raw: str, settings: AuthSettings) -> TokenClaims:
    """Decode *raw* and enforce that it is a refresh token."""
    claims = decode_token(raw, settings)
    if claims.token_type != _REFRESH:
        raise TokenInvalidError("Expected a refresh token.")
    return claims
