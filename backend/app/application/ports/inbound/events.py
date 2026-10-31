from typing import Protocol

from app.application.dto.commands import CreateEventCommand, EventActionCommand, UpdateEventCommand
from app.application.dto.queries import GetEventQuery, SearchEventsQuery
from app.application.dto.read_models import Page
from app.domain.models.event import Event


class CreateEvent(Protocol):
    async def execute(self, cmd: CreateEventCommand) -> Event: ...


class UpdateEvent(Protocol):
    async def execute(self, cmd: UpdateEventCommand) -> Event: ...


class GetEvent(Protocol):
    async def execute(self, query: GetEventQuery) -> Event: ...


class SearchEvents(Protocol):
    async def execute(self, query: SearchEventsQuery) -> Page[Event]: ...


class DeleteEvent(Protocol):
    async def execute(self, cmd: EventActionCommand) -> None: ...


class PublishEvent(Protocol):
    async def execute(self, cmd: EventActionCommand) -> Event: ...


class FinishEvent(Protocol):
    async def execute(self, cmd: EventActionCommand) -> Event: ...


class CancelEvent(Protocol):
    async def execute(self, cmd: EventActionCommand) -> Event: ...
