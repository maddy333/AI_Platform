"""User repository — all database access for the User aggregate."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiplatform.auth.domain.errors import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from aiplatform.auth.domain.models import Role, User
from aiplatform.auth.hashing import hash_password, needs_rehash, verify_password
from aiplatform.auth.orm.user import UserORM


def _to_domain(row: UserORM) -> User:
    return User(
        id=row.id,
        tenant_id=row.tenant_id,
        email=row.email,
        full_name=row.full_name,
        roles=frozenset(Role(r) for r in row.roles),
        is_active=row.is_active,
        created_at=row.created_at,
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        full_name: str,
        password: str,
        roles: frozenset[Role],
    ) -> User:
        existing = await self._session.scalar(
            select(UserORM).where(UserORM.email == email)
        )
        if existing is not None:
            raise UserAlreadyExistsError(f"User with email {email!r} already exists.")

        row = UserORM(
            tenant_id=tenant_id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            roles=[r.value for r in roles],
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        row = await self._session.get(UserORM, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found.")
        return _to_domain(row)

    async def get_by_email(self, email: str) -> User:
        row = await self._session.scalar(
            select(UserORM).where(UserORM.email == email, UserORM.is_active.is_(True))
        )
        if row is None:
            raise UserNotFoundError(f"User with email {email!r} not found.")
        return _to_domain(row)

    async def authenticate(self, email: str, password: str) -> User:
        row = await self._session.scalar(
            select(UserORM).where(UserORM.email == email)
        )
        if row is None:
            raise InvalidCredentialsError("Invalid email or password.")
        verify_password(password, row.password_hash)
        if needs_rehash(row.password_hash):
            row.password_hash = hash_password(password)
            await self._session.flush()
        if not row.is_active:
            raise InvalidCredentialsError("Account is disabled.")
        return _to_domain(row)

    async def update_roles(self, user_id: uuid.UUID, roles: frozenset[Role]) -> User:
        row = await self._session.get(UserORM, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found.")
        row.roles = [r.value for r in roles]
        await self._session.flush()
        return _to_domain(row)

    async def deactivate(self, user_id: uuid.UUID) -> None:
        row = await self._session.get(UserORM, user_id)
        if row is None:
            raise UserNotFoundError(f"User {user_id} not found.")
        row.is_active = False
        await self._session.flush()
