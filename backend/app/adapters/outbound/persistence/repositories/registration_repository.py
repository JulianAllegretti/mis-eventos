from datetime import datetime
from uuid import UUID

from sqlalchemy import func, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.mappers import (
    event_to_domain,
    registration_to_domain,
    registration_to_table,
    session_registration_to_domain,
    session_registration_to_table,
    session_to_domain,
    user_to_domain,
)
from app.adapters.outbound.persistence.tables import (
    EventTable,
    RegistrationTable,
    SessionRegistrationTable,
    SessionTable,
    UserTable,
)
from app.domain.errors import AlreadyRegistered
from app.domain.models.event import Event
from app.domain.models.registration import Registration, SessionRegistration
from app.domain.models.session import Session
from app.domain.models.user import User


class SqlRegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self, user_id: UUID, event_id: UUID) -> Registration | None:
        result = await self._session.exec(
            select(RegistrationTable).where(
                col(RegistrationTable.user_id) == user_id,
                col(RegistrationTable.event_id) == event_id,
                col(RegistrationTable.cancelled_at).is_(None),
            )
        )
        row = result.first()
        return registration_to_domain(row) if row else None

    async def add(self, registration: Registration) -> None:
        self._session.add(registration_to_table(registration))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Índice único parcial (user_id, event_id) WHERE cancelled_at IS NULL.
            raise AlreadyRegistered("Ya estás inscrito en este evento") from exc

    async def cancel(self, user_id: UUID, event_id: UUID, now: datetime) -> bool:
        connection = await self._session.connection()
        result = await connection.execute(
            update(RegistrationTable)
            .where(
                col(RegistrationTable.user_id) == user_id,
                col(RegistrationTable.event_id) == event_id,
                col(RegistrationTable.cancelled_at).is_(None),
            )
            .values(cancelled_at=now)
        )
        return result.rowcount == 1

    async def exists_for_event(self, event_id: UUID) -> bool:
        result = await self._session.exec(
            select(func.count())
            .select_from(RegistrationTable)
            .where(col(RegistrationTable.event_id) == event_id)
        )
        return result.one() > 0

    async def list_active_for_user(self, user_id: UUID) -> list[tuple[Registration, Event]]:
        rows = await self._session.exec(
            select(RegistrationTable, EventTable)
            .join(EventTable, col(EventTable.id) == col(RegistrationTable.event_id))
            .where(
                col(RegistrationTable.user_id) == user_id,
                col(RegistrationTable.cancelled_at).is_(None),
            )
            .order_by(col(EventTable.start_at), col(EventTable.id))
        )
        return [(registration_to_domain(r), event_to_domain(e)) for r, e in rows]

    async def list_attendees(
        self, event_id: UUID, limit: int, offset: int
    ) -> tuple[list[tuple[Registration, User]], int]:
        active = (
            col(RegistrationTable.event_id) == event_id,
            col(RegistrationTable.cancelled_at).is_(None),
        )
        total = (
            await self._session.exec(
                select(func.count()).select_from(RegistrationTable).where(*active)
            )
        ).one()
        rows = await self._session.exec(
            select(RegistrationTable, UserTable)
            .join(UserTable, col(UserTable.id) == col(RegistrationTable.user_id))
            .where(*active)
            .order_by(col(RegistrationTable.created_at), col(RegistrationTable.id))
            .limit(limit)
            .offset(offset)
        )
        return [(registration_to_domain(r), user_to_domain(u)) for r, u in rows], total


class SqlSessionRegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_user(self, user_id: UUID) -> None:
        connection = await self._session.connection()
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"sreg:{user_id}"}
        )

    async def get_active(self, user_id: UUID, session_id: UUID) -> SessionRegistration | None:
        result = await self._session.exec(
            select(SessionRegistrationTable).where(
                col(SessionRegistrationTable.user_id) == user_id,
                col(SessionRegistrationTable.session_id) == session_id,
                col(SessionRegistrationTable.cancelled_at).is_(None),
            )
        )
        row = result.first()
        return session_registration_to_domain(row) if row else None

    async def add(self, registration: SessionRegistration) -> None:
        self._session.add(session_registration_to_table(registration))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise AlreadyRegistered("Ya estás inscrito en esta sesión") from exc

    async def cancel(self, user_id: UUID, session_id: UUID, now: datetime) -> bool:
        connection = await self._session.connection()
        result = await connection.execute(
            update(SessionRegistrationTable)
            .where(
                col(SessionRegistrationTable.user_id) == user_id,
                col(SessionRegistrationTable.session_id) == session_id,
                col(SessionRegistrationTable.cancelled_at).is_(None),
            )
            .values(cancelled_at=now)
        )
        return result.rowcount == 1

    async def cancel_all_for_event(
        self, user_id: UUID, event_id: UUID, now: datetime
    ) -> list[UUID]:
        connection = await self._session.connection()
        event_sessions = select(col(SessionTable.id)).where(col(SessionTable.event_id) == event_id)
        result = await connection.execute(
            update(SessionRegistrationTable)
            .where(
                col(SessionRegistrationTable.user_id) == user_id,
                col(SessionRegistrationTable.cancelled_at).is_(None),
                col(SessionRegistrationTable.session_id).in_(event_sessions),
            )
            .values(cancelled_at=now)
            .returning(col(SessionRegistrationTable.session_id))
        )
        return [row[0] for row in result]

    async def has_overlap(self, user_id: UUID, start_at: datetime, end_at: datetime) -> bool:
        result = await self._session.exec(
            select(func.count())
            .select_from(SessionRegistrationTable)
            .join(SessionTable, col(SessionTable.id) == col(SessionRegistrationTable.session_id))
            .where(
                col(SessionRegistrationTable.user_id) == user_id,
                col(SessionRegistrationTable.cancelled_at).is_(None),
                col(SessionTable.start_at) < end_at,
                col(SessionTable.end_at) > start_at,
            )
        )
        return result.one() > 0

    async def list_active_for_user(
        self, user_id: UUID
    ) -> list[tuple[SessionRegistration, Session]]:
        rows = await self._session.exec(
            select(SessionRegistrationTable, SessionTable)
            .join(SessionTable, col(SessionTable.id) == col(SessionRegistrationTable.session_id))
            .where(
                col(SessionRegistrationTable.user_id) == user_id,
                col(SessionRegistrationTable.cancelled_at).is_(None),
            )
            .order_by(col(SessionTable.start_at), col(SessionTable.id))
        )
        return [(session_registration_to_domain(r), session_to_domain(s)) for r, s in rows]
