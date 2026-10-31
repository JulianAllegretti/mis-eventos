from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.outbound.persistence.repositories.event_repository import SqlEventRepository
from app.adapters.outbound.persistence.repositories.registration_repository import (
    SqlRegistrationRepository,
    SqlSessionRegistrationRepository,
)
from app.adapters.outbound.persistence.repositories.session_repository import SqlSessionRepository
from app.adapters.outbound.persistence.repositories.speaker_repository import SqlSpeakerRepository
from app.adapters.outbound.persistence.repositories.user_repository import SqlUserRepository


class SqlUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlUserRepository(self._session)
        self.events = SqlEventRepository(self._session)
        self.speakers = SqlSpeakerRepository(self._session)
        self.sessions = SqlSessionRepository(self._session)
        self.registrations = SqlRegistrationRepository(self._session)
        self.session_registrations = SqlSessionRegistrationRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            await session.rollback()  # no-op si ya se hizo commit
        finally:
            await session.close()

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork usado fuera de 'async with'")
        return self._session
