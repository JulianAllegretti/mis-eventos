from uuid import UUID

from app.application.dto.commands import (
    CreateSpeakerCommand,
    SpeakerActionCommand,
    UpdateSpeakerCommand,
)
from app.application.dto.paging import resolve_page
from app.application.dto.queries import GetSpeakerQuery, ListSpeakersQuery
from app.application.dto.read_models import Page
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.domain.errors import NotFound, ValidationFailed
from app.domain.models.speaker import Speaker
from app.domain.models.user import User
from app.domain.services.permissions import MANAGERS, ensure_role
from app.domain.services.speaker_rules import validate_speaker_data

_UPDATABLE = frozenset({"name", "email", "bio"})


async def _load(uow: UnitOfWork, speaker_id: UUID) -> Speaker:
    speaker = await uow.speakers.get(speaker_id)
    if speaker is None:
        raise NotFound("Ponente no encontrado")
    return speaker


def _ensure_manager(actor: User) -> None:
    ensure_role(actor, *MANAGERS)


class CreateSpeakerUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: CreateSpeakerCommand) -> Speaker:
        _ensure_manager(cmd.actor)
        name, email, bio = validate_speaker_data(cmd.name, cmd.email, cmd.bio)
        speaker = Speaker.new(
            name=name, email=email, bio=bio, created_by_id=cmd.actor.id, now=self._clock.now()
        )
        async with self._uow_factory() as uow:
            await uow.speakers.add(speaker)
            await uow.commit()
        return speaker


class UpdateSpeakerUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: UpdateSpeakerCommand) -> Speaker:
        _ensure_manager(cmd.actor)
        unknown = set(cmd.changes) - _UPDATABLE
        if unknown:
            raise ValidationFailed("Campos no editables", sorted(unknown))
        if "name" in cmd.changes and cmd.changes["name"] is None:
            raise ValidationFailed("Campos que no admiten nulo", ["name"])

        async with self._uow_factory() as uow:
            speaker = await _load(uow, cmd.speaker_id)
            name, email, bio = validate_speaker_data(
                cmd.changes.get("name", speaker.name),
                cmd.changes.get("email", speaker.email),
                cmd.changes.get("bio", speaker.bio),
            )
            speaker.name, speaker.email, speaker.bio = name, email, bio
            await uow.speakers.update(speaker)
            await uow.commit()
        return speaker


class DeleteSpeakerUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: SpeakerActionCommand) -> None:
        _ensure_manager(cmd.actor)
        async with self._uow_factory() as uow:
            speaker = await _load(uow, cmd.speaker_id)
            await uow.speakers.delete(speaker.id)
            await uow.commit()


class GetSpeakerUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: GetSpeakerQuery) -> Speaker:
        _ensure_manager(query.actor)
        async with self._uow_factory() as uow:
            return await _load(uow, query.speaker_id)


class ListSpeakersUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListSpeakersQuery) -> Page[Speaker]:
        _ensure_manager(query.actor)
        page, limit, offset = resolve_page(query.page, query.page_size)
        q = query.q.strip() if query.q else None
        async with self._uow_factory() as uow:
            items, total = await uow.speakers.list_page(q or None, limit, offset)
        return Page(items=items, total=total, page=page, page_size=query.page_size)
