"""Async SQLAlchemy engine and session factory.

The engine is created once at application startup and disposed at shutdown.
Repositories receive sessions via ``get_session()``, a FastAPI-compatible
async generator dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from aiplatform.core.config import DatabaseSettings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create the engine singleton from *settings*.

    Called once inside the application lifespan; subsequent calls are no-ops
    (the singleton is returned immediately).
    """
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        return _engine

    _engine = create_async_engine(
        settings.url,
        echo=settings.echo_sql,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _engine


async def dispose_engine() -> None:
    """Dispose the engine and reset the singleton.  Called at shutdown."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        msg = "Database engine has not been initialised. Call init_engine() first."
        raise RuntimeError(msg)
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional ``AsyncSession``.

    The session is committed on success and rolled back on any exception.
    """
    if _session_factory is None:
        msg = "Session factory is not ready. Call init_engine() during app startup."
        raise RuntimeError(msg)

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
