"""Database health check registered with the platform HealthRegistry."""

from __future__ import annotations

from sqlalchemy import text

from aiplatform.db.engine import get_engine


async def check_database() -> None:
    """Ping the database with ``SELECT 1``.

    Raises on any connection or query failure so the health registry can mark
    the service as not-ready.
    """
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
