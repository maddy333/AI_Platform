"""Tenant ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list[UserORM]] = relationship(  # type: ignore[name-defined]
        "UserORM", back_populates="tenant", lazy="noload"
    )
    api_keys: Mapped[list[APIKeyORM]] = relationship(  # type: ignore[name-defined]
        "APIKeyORM", back_populates="tenant", lazy="noload"
    )
