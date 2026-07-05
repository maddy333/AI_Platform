"""APIKey ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class APIKeyORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[uuid.UUID | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[uuid.UUID | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[TenantORM] = relationship(  # type: ignore[name-defined]
        "TenantORM", back_populates="api_keys", lazy="noload"
    )
    user: Mapped[UserORM] = relationship(  # type: ignore[name-defined]
        "UserORM", back_populates="api_keys", lazy="noload"
    )
