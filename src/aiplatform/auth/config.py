"""Auth subsystem configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr


class AuthSettings(BaseModel):
    """JWT and session configuration."""

    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production-min-32-chars!!"),
        description="HS256 signing secret; must be ≥32 chars in production.",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # API key settings
    api_key_prefix: str = "aip"
    api_key_bytes: int = Field(default=32, ge=16)

    # Password policy
    min_password_length: int = Field(default=12, ge=8)
