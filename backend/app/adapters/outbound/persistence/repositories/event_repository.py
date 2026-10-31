from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_
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
from app.domain.models.event import Event, EventStatus


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
