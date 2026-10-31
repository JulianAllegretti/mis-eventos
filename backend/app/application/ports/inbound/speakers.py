from typing import Protocol

from app.application.dto.commands import (
    CreateSpeakerCommand,
    SpeakerActionCommand,
    UpdateSpeakerCommand,
)
from app.application.dto.queries import GetSpeakerQuery, ListSpeakersQuery
from app.application.dto.read_models import Page
from app.domain.models.speaker import Speaker


class CreateSpeaker(Protocol):
    async def execute(self, cmd: CreateSpeakerCommand) -> Speaker: ...


class UpdateSpeaker(Protocol):
    async def execute(self, cmd: UpdateSpeakerCommand) -> Speaker: ...


class DeleteSpeaker(Protocol):
    async def execute(self, cmd: SpeakerActionCommand) -> None: ...


class GetSpeaker(Protocol):
    async def execute(self, query: GetSpeakerQuery) -> Speaker: ...


class ListSpeakers(Protocol):
    async def execute(self, query: ListSpeakersQuery) -> Page[Speaker]: ...
