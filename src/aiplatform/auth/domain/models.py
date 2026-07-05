"""Auth domain models — pure Python, no ORM dependency.

These dataclasses represent the authoritative domain objects.  ORM models live
in ``auth/orm/`` and map to the same concepts; repositories translate between
the two layers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Role(StrEnum):
    """Platform RBAC roles, ordered from least to most privileged."""

    VIEWER = "viewer"
    DEVELOPER = "developer"
    TENANT_ADMIN = "tenant_admin"
    SUPER_ADMIN = "super_admin"


class Permission(StrEnum):
    """Fine-grained permission flags checked by the dependency layer."""

    # Gateway
    GATEWAY_READ = "gateway:read"
    GATEWAY_WRITE = "gateway:write"

    # Prompt registry
    PROMPT_READ = "prompt:read"
    PROMPT_WRITE = "prompt:write"
    PROMPT_APPROVE = "prompt:approve"

    # Model management
    MODEL_READ = "model:read"
    MODEL_WRITE = "model:write"

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"

    # Tenant management
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"

    # API key management
    API_KEY_READ = "apikey:read"
    API_KEY_WRITE = "apikey:write"

    # Evaluation
    EVAL_READ = "eval:read"
    EVAL_WRITE = "eval:write"

    # Fine-tuning
    FINETUNE_READ = "finetune:read"
    FINETUNE_WRITE = "finetune:write"

    # Admin
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"


# Role → permission set mapping (additive: higher roles include lower ones)
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {
            Permission.GATEWAY_READ,
            Permission.PROMPT_READ,
            Permission.MODEL_READ,
            Permission.EVAL_READ,
        }
    ),
    Role.DEVELOPER: frozenset(
        {
            Permission.GATEWAY_READ,
            Permission.GATEWAY_WRITE,
            Permission.PROMPT_READ,
            Permission.PROMPT_WRITE,
            Permission.MODEL_READ,
            Permission.EVAL_READ,
            Permission.EVAL_WRITE,
            Permission.FINETUNE_READ,
            Permission.FINETUNE_WRITE,
            Permission.API_KEY_READ,
            Permission.API_KEY_WRITE,
        }
    ),
    Role.TENANT_ADMIN: frozenset(
        {
            Permission.GATEWAY_READ,
            Permission.GATEWAY_WRITE,
            Permission.PROMPT_READ,
            Permission.PROMPT_WRITE,
            Permission.PROMPT_APPROVE,
            Permission.MODEL_READ,
            Permission.MODEL_WRITE,
            Permission.USER_READ,
            Permission.USER_WRITE,
            Permission.TENANT_READ,
            Permission.EVAL_READ,
            Permission.EVAL_WRITE,
            Permission.FINETUNE_READ,
            Permission.FINETUNE_WRITE,
            Permission.API_KEY_READ,
            Permission.API_KEY_WRITE,
        }
    ),
    Role.SUPER_ADMIN: frozenset(Permission),  # all permissions
}


@dataclass(frozen=True)
class Tenant:
    """A tenant (organisation) within the platform."""

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime | None = None


@dataclass(frozen=True)
class User:
    """A platform user belonging to a tenant."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    roles: frozenset[Role]
    is_active: bool = True
    created_at: datetime | None = None

    @property
    def permissions(self) -> frozenset[Permission]:
        return frozenset(
            perm
            for role in self.roles
            for perm in ROLE_PERMISSIONS.get(role, frozenset())
        )

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_role(self, role: Role) -> bool:
        return role in self.roles


@dataclass(frozen=True)
class APIKey:
    """An API key bound to a user and tenant."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    key_prefix: str
    key_hash: str
    roles: frozenset[Role]
    is_active: bool = True
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class TokenClaims:
    """Decoded, validated JWT claims."""

    sub: uuid.UUID
    tenant_id: uuid.UUID
    roles: frozenset[Role]
    jti: uuid.UUID
    token_type: str
    exp: datetime
    iat: datetime
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditEvent:
    """Immutable record of a security-relevant action."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    outcome: str
    detail: dict[str, str] = field(default_factory=dict)
