"""SQLAlchemy declarative base with shared column conventions.

Every ORM model inherits from ``Base``.  The ``TimestampMixin`` and
``UUIDPrimaryKeyMixin`` provide columns that every entity shares: a UUID
primary key (server-generated) and ISO-8601 UTC timestamps.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base.

    A single base keeps the MetaData object coherent so Alembic can
    auto-generate migrations from all models in one pass.
    """


class UUIDPrimaryKeyMixin:
    """UUID primary key, generated server-side by PostgreSQL."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        sort_order=-100,
    )


class TimestampMixin:
    """Automatic UTC created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )
