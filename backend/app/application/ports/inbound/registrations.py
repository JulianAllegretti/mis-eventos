from typing import Protocol

from app.application.dto.commands import EventActionCommand, SessionActionCommand
from app.application.dto.queries import ListAttendeesQuery, ListMyRegistrationsQuery
from app.application.dto.read_models import AttendeeView, MyRegistration, Page
from app.domain.models.registration import Registration, SessionRegistration


class RegisterToEvent(Protocol):
    async def execute(self, cmd: EventActionCommand) -> Registration: ...


class CancelEventRegistration(Protocol):
    async def execute(self, cmd: EventActionCommand) -> None: ...


class ListMyRegistrations(Protocol):
    async def execute(self, query: ListMyRegistrationsQuery) -> list[MyRegistration]: ...


class ListEventAttendees(Protocol):
    async def execute(self, query: ListAttendeesQuery) -> Page[AttendeeView]: ...


class RegisterToSession(Protocol):
    async def execute(self, cmd: SessionActionCommand) -> SessionRegistration: ...


class CancelSessionRegistration(Protocol):
    async def execute(self, cmd: SessionActionCommand) -> None: ...
