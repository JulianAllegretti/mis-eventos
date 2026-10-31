from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.mappers import speaker_to_domain, speaker_to_table
from app.adapters.outbound.persistence.sql_utils import LIKE_ESCAPE, contains_pattern
from app.adapters.outbound.persistence.tables import SpeakerTable
from app.domain.models.speaker import Speaker


class SqlSpeakerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, speaker_id: UUID) -> Speaker | None:
        row = await self._session.get(SpeakerTable, speaker_id)
        return speaker_to_domain(row) if row else None

    async def get_many(self, speaker_ids: list[UUID]) -> list[Speaker]:
        if not speaker_ids:
            return []
        rows = await self._session.exec(
            select(SpeakerTable).where(col(SpeakerTable.id).in_(speaker_ids))
        )
        return [speaker_to_domain(r) for r in rows]

    async def add(self, speaker: Speaker) -> None:
        self._session.add(speaker_to_table(speaker))
        await self._session.flush()

    async def update(self, speaker: Speaker) -> None:
        row = await self._session.get(SpeakerTable, speaker.id)
        if row is None:
            return
        row.name, row.email, row.bio = speaker.name, speaker.email, speaker.bio
        await self._session.flush()

    async def delete(self, speaker_id: UUID) -> None:
        row = await self._session.get(SpeakerTable, speaker_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[Speaker], int]:
        conditions = []
        if q:
            conditions.append(
                SpeakerTable.name.ilike(  # type: ignore[attr-defined]
                    contains_pattern(q), escape=LIKE_ESCAPE
                )
            )
        total = (
            await self._session.exec(
                select(func.count()).select_from(SpeakerTable).where(*conditions)
            )
        ).one()
        rows = await self._session.exec(
            select(SpeakerTable)
            .where(*conditions)
            .order_by(SpeakerTable.name, SpeakerTable.id)  # type: ignore[arg-type]
            .limit(limit)
            .offset(offset)
        )
        return [speaker_to_domain(r) for r in rows], total
