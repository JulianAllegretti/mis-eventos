from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, text, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.mappers import (
    apply_event_to_row,
    event_to_domain,
    event_to_table,
)
from app.adapters.outbound.persistence.sql_utils import LIKE_ESCAPE, contains_pattern
from app.adapters.outbound.persistence.tables import EventTable
from app.application.dto.queries import EventSearchCriteria
from app.domain.models.event import ClosedSource, Event, EventStatus

# Clave del advisory lock que evita que varios workers ejecuten el cierre automático a la vez.
_FINISH_JOB_LOCK_KEY = 7_204_001


class SqlEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: UUID) -> Event | None:
        row = await self._session.get(EventTable, event_id)
        return event_to_domain(row) if row else None

    async def add(self, event: Event) -> None:
        self._session.add(event_to_table(event))
        await self._session.flush()

    async def update(self, event: Event) -> None:
        row = await self._session.get(EventTable, event.id)
        if row is None:
            return
        apply_event_to_row(event, row)
        await self._session.flush()

    async def delete(self, event_id: UUID) -> None:
        row = await self._session.get(EventTable, event_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def search(self, criteria: EventSearchCriteria) -> tuple[list[Event], int]:
        conditions = self._conditions(criteria)
        total = (
            await self._session.exec(
                select(func.count()).select_from(EventTable).where(*conditions)
            )
        ).one()
        rows = await self._session.exec(
            select(EventTable)
            .where(*conditions)
            .order_by(col(EventTable.start_at), col(EventTable.id))
            .limit(criteria.limit)
            .offset(criteria.offset)
        )
        return [event_to_domain(r) for r in rows], total

    async def try_increment_registered(self, event_id: UUID, now: datetime) -> bool:
        """Toma un cupo con una sola sentencia atómica: no hay ventana entre leer y escribir."""
        connection = await self._session.connection()
        result = await connection.execute(
            update(EventTable)
            .where(
                col(EventTable.id) == event_id,
                col(EventTable.registered_count) < col(EventTable.capacity),
                col(EventTable.status) == EventStatus.PUBLISHED.value,
                col(EventTable.end_at) >= now,
            )
            .values(registered_count=col(EventTable.registered_count) + 1)
        )
        return result.rowcount == 1

    async def decrement_registered(self, event_id: UUID) -> None:
        connection = await self._session.connection()
        await connection.execute(
            update(EventTable)
            .where(col(EventTable.id) == event_id, col(EventTable.registered_count) > 0)
            .values(registered_count=col(EventTable.registered_count) - 1)
        )

    async def finish_expired(self, now: datetime) -> list[UUID]:
        connection = await self._session.connection()
        locked = (
            await connection.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": _FINISH_JOB_LOCK_KEY}
            )
        ).scalar_one()
        if not locked:
            return []  # otro worker ya está ejecutando el cierre
        result = await connection.execute(
            update(EventTable)
            .where(
                col(EventTable.status) == EventStatus.PUBLISHED.value,
                col(EventTable.end_at) < now,
            )
            .values(
                status=EventStatus.FINISHED.value,
                closed_at=now,
                closed_by_id=None,
                closed_source=ClosedSource.SCHEDULER.value,
                updated_at=now,
            )
            .returning(col(EventTable.id))
        )
        return [row[0] for row in result]

    async def list_open_availability(self, now: datetime) -> list[tuple[UUID, int]]:
        rows = await self._session.exec(
            select(
                col(EventTable.id), col(EventTable.capacity) - col(EventTable.registered_count)
            ).where(
                col(EventTable.status) == EventStatus.PUBLISHED.value,
                col(EventTable.end_at) >= now,
            )
        )
        return [(event_id, available) for event_id, available in rows]

    @staticmethod
    def _conditions(criteria: EventSearchCriteria) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if criteria.q:
            # El texto del usuario viaja como parámetro ligado; escape_like neutraliza % y _.
            conditions.append(
                col(EventTable.name).ilike(contains_pattern(criteria.q), escape=LIKE_ESCAPE)
            )
        if criteria.organizer_id is not None:
            conditions.append(col(EventTable.organizer_id) == criteria.organizer_id)
        if criteria.exclude_drafts:
            conditions.append(col(EventTable.status) != EventStatus.DRAFT.value)
        if criteria.status is not None:
            conditions.append(_status_condition(criteria.status, criteria.now))
        return conditions


def _status_condition(status: EventStatus, now: datetime) -> ColumnElement[bool]:
    """Traduce el estado efectivo (ADR 0008) a SQL: un publicado vencido cuenta como finalizado."""
    stored = col(EventTable.status)
    expired = col(EventTable.end_at) < now
    if status is EventStatus.PUBLISHED:
        return and_(stored == EventStatus.PUBLISHED.value, ~expired)
    if status is EventStatus.FINISHED:
        return or_(
            stored == EventStatus.FINISHED.value,
            and_(stored == EventStatus.PUBLISHED.value, expired),
        )
    return stored == status.value
