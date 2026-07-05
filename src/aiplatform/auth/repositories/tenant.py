"""Tenant repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiplatform.auth.domain.errors import TenantNotFoundError
from aiplatform.auth.domain.models import Tenant
from aiplatform.auth.orm.tenant import TenantORM


def _to_domain(row: TenantORM) -> Tenant:
    return Tenant(
        id=row.id,
        name=row.name,
        slug=row.slug,
        is_active=row.is_active,
        created_at=row.created_at,
    )


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, slug: str) -> Tenant:
        row = TenantORM(name=name, slug=slug, is_active=True)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant:
        row = await self._session.get(TenantORM, tenant_id)
        if row is None:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found.")
        return _to_domain(row)

    async def get_by_slug(self, slug: str) -> Tenant:
        row = await self._session.scalar(
            select(TenantORM).where(TenantORM.slug == slug)
        )
        if row is None:
            raise TenantNotFoundError(f"Tenant with slug {slug!r} not found.")
        return _to_domain(row)

    async def list_active(self) -> list[Tenant]:
        rows = await self._session.scalars(
            select(TenantORM).where(TenantORM.is_active.is_(True)).order_by(TenantORM.name)
        )
        return [_to_domain(r) for r in rows]
