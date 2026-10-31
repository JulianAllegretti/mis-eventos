from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from app.application.ports.outbound.repositories import (
    EventRepository,
    RegistrationRepository,
    SessionRegistrationRepository,
    SessionRepository,
    SpeakerRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    """Transacción que agrupa los repositorios. Si no se hace commit, se revierte al salir."""

    @property
    def users(self) -> UserRepository: ...

    @property
    def events(self) -> EventRepository: ...

    @property
    def speakers(self) -> SpeakerRepository: ...

    @property
    def sessions(self) -> SessionRepository: ...

    @property
    def registrations(self) -> RegistrationRepository: ...

    @property
    def session_registrations(self) -> SessionRegistrationRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
