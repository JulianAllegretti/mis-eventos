from typing import Protocol

from app.application.dto.commands import (
    CreateSessionCommand,
    SessionActionCommand,
    UpdateSessionCommand,
)
from app.application.dto.queries import ListEventSessionsQuery
from app.application.dto.read_models import SessionView


class CreateSession(Protocol):
    async def execute(self, cmd: CreateSessionCommand) -> SessionView: ...


class UpdateSession(Protocol):
    async def execute(self, cmd: UpdateSessionCommand) -> SessionView: ...


class DeleteSession(Protocol):
    async def execute(self, cmd: SessionActionCommand) -> None: ...


class ListEventSessions(Protocol):
    async def execute(self, query: ListEventSessionsQuery) -> list[SessionView]: ...
