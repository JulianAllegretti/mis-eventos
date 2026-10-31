from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.mappers import user_to_domain, user_to_table
from app.adapters.outbound.persistence.sql_utils import LIKE_ESCAPE, contains_pattern
from app.adapters.outbound.persistence.tables import UserTable
from app.domain.errors import EmailAlreadyRegistered
from app.domain.models.user import User


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserTable, user_id)
        return user_to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.exec(select(UserTable).where(UserTable.email == email))
        row = result.first()
        return user_to_domain(row) if row else None

    async def add(self, user: User) -> None:
        self._session.add(user_to_table(user))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegistered() from exc

    async def update(self, user: User) -> None:
        row = await self._session.get(UserTable, user.id)
        if row is None:
            return
        row.full_name = user.full_name
        row.role = user.role.value
        row.is_active = user.is_active
        await self._session.flush()

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[User], int]:
        conditions = []
        if q:
            pattern = contains_pattern(q)
            conditions.append(
                or_(
                    UserTable.email.ilike(pattern, escape=LIKE_ESCAPE),  # type: ignore[attr-defined]
                    UserTable.full_name.ilike(pattern, escape=LIKE_ESCAPE),  # type: ignore[attr-defined]
                )
            )
        total = (
            await self._session.exec(select(func.count()).select_from(UserTable).where(*conditions))
        ).one()
        rows = await self._session.exec(
            select(UserTable)
            .where(*conditions)
            .order_by(UserTable.created_at, UserTable.id)  # type: ignore[arg-type]
            .limit(limit)
            .offset(offset)
        )
        return [user_to_domain(r) for r in rows], total
