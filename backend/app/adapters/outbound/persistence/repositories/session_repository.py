from datetime import datetime
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.mappers import session_to_domain, session_to_table
from app.adapters.outbound.persistence.tables import SessionTable
from app.domain.errors import ScheduleConflict
from app.domain.models.session import Session

SPEAKER_OVERLAP_CONSTRAINT = "ex_sessions_speaker_no_overlap"


class SqlSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, session_id: UUID) -> Session | None:
        row = await self._session.get(SessionTable, session_id)
        return session_to_domain(row) if row else None

    async def add(self, session: Session) -> None:
        self._session.add(session_to_table(session))
        await self._flush()

    async def update(self, session: Session) -> None:
        row = await self._session.get(SessionTable, session.id)
        if row is None:
            return
        row.speaker_id = session.speaker_id
        row.title = session.title
        row.description = session.description
        row.start_at = session.start_at
        row.end_at = session.end_at
        row.capacity = session.capacity
        await self._flush()

    async def delete(self, session_id: UUID) -> None:
        row = await self._session.get(SessionTable, session_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_for_event(self, event_id: UUID) -> list[Session]:
        rows = await self._session.exec(
            select(SessionTable)
            .where(col(SessionTable.event_id) == event_id)
            .order_by(col(SessionTable.start_at), col(SessionTable.id))
        )
        return [session_to_domain(r) for r in rows]

    async def count_for_speaker(self, speaker_id: UUID) -> int:
        result = await self._session.exec(
            select(func.count())
            .select_from(SessionTable)
            .where(col(SessionTable.speaker_id) == speaker_id)
        )
        return result.one()

    async def speaker_has_overlap(
        self, speaker_id: UUID, start_at: datetime, end_at: datetime, exclude_id: UUID | None
    ) -> bool:
        # Rangos [inicio, fin): una sesión que empieza justo cuando otra termina no se solapa.
        conditions = [
            col(SessionTable.speaker_id) == speaker_id,
            col(SessionTable.start_at) < end_at,
            col(SessionTable.end_at) > start_at,
        ]
        if exclude_id is not None:
            conditions.append(col(SessionTable.id) != exclude_id)
        result = await self._session.exec(
            select(func.count()).select_from(SessionTable).where(*conditions)
        )
        return result.one() > 0

    async def try_increment_registered(self, session_id: UUID) -> bool:
        connection = await self._session.connection()
        result = await connection.execute(
            update(SessionTable)
            .where(
                col(SessionTable.id) == session_id,
                col(SessionTable.registered_count) < col(SessionTable.capacity),
            )
            .values(registered_count=col(SessionTable.registered_count) + 1)
        )
        return result.rowcount == 1

    async def decrement_registered(self, session_id: UUID) -> None:
        connection = await self._session.connection()
        await connection.execute(
            update(SessionTable)
            .where(col(SessionTable.id) == session_id, col(SessionTable.registered_count) > 0)
            .values(registered_count=col(SessionTable.registered_count) - 1)
        )

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # La restricción EXCLUDE cubre la carrera entre dos sesiones simultáneas del ponente.
            if SPEAKER_OVERLAP_CONSTRAINT in str(exc.orig):
                raise ScheduleConflict("El ponente ya tiene una sesión en ese horario") from exc
            raise
