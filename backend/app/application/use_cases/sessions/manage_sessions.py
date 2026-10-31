from typing import Any
from uuid import UUID

from app.application.dto.commands import (
    CreateSessionCommand,
    SessionActionCommand,
    UpdateSessionCommand,
)
from app.application.dto.queries import ListEventSessionsQuery
from app.application.dto.read_models import SessionView
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.event_sync import EventSync
from app.application.use_cases.events._access import load_managed_event, load_visible_event
from app.domain.errors import Conflict, NotFound, ScheduleConflict, ValidationFailed
from app.domain.models.session import Session
from app.domain.models.speaker import Speaker
from app.domain.services.event_lifecycle import ensure_editable
from app.domain.services.scheduling import SessionData, validate_session_data

_UPDATABLE = frozenset({"speaker_id", "title", "description", "start_at", "end_at", "capacity"})
_NOT_NULLABLE = _UPDATABLE - {"description"}
_SCHEDULE_FIELDS = frozenset({"speaker_id", "start_at", "end_at"})


async def _require_speaker(uow: UnitOfWork, speaker_id: UUID) -> Speaker:
    speaker = await uow.speakers.get(speaker_id)
    if speaker is None:
        raise NotFound("Ponente no encontrado")
    return speaker


async def _load_session(uow: UnitOfWork, session_id: UUID) -> Session:
    session = await uow.sessions.get(session_id)
    if session is None:
        raise NotFound("Sesión no encontrada")
    return session


class CreateSessionUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def execute(self, cmd: CreateSessionCommand) -> SessionView:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            ensure_editable(event, now)
            speaker = await _require_speaker(uow, cmd.speaker_id)
            data = validate_session_data(
                SessionData(
                    speaker_id=speaker.id,
                    title=cmd.title,
                    description=cmd.description,
                    start_at=cmd.start_at,
                    end_at=cmd.end_at,
                    capacity=cmd.capacity,
                ),
                event,
            )
            if await uow.sessions.speaker_has_overlap(speaker.id, data.start_at, data.end_at, None):
                raise ScheduleConflict("El ponente ya tiene una sesión en ese horario")

            session = Session.new(
                event_id=event.id,
                speaker_id=speaker.id,
                title=data.title,
                description=data.description,
                start_at=data.start_at,
                end_at=data.end_at,
                capacity=data.capacity,
                now=now,
            )
            await uow.sessions.add(session)  # la restricción EXCLUDE cubre la carrera
            await uow.commit()
        await self._sync.counts_changed()
        return SessionView(session=session, speaker=speaker)


class UpdateSessionUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def execute(self, cmd: UpdateSessionCommand) -> SessionView:
        unknown = set(cmd.changes) - _UPDATABLE
        if unknown:
            raise ValidationFailed("Campos no editables", sorted(unknown))
        nulls = sorted(k for k in _NOT_NULLABLE if k in cmd.changes and cmd.changes[k] is None)
        if nulls:
            raise ValidationFailed("Campos que no admiten nulo", nulls)

        now = self._clock.now()
        async with self._uow_factory() as uow:
            session = await _load_session(uow, cmd.session_id)
            event = await load_managed_event(uow, session.event_id, cmd.actor)
            ensure_editable(event, now)
            if session.registered_count > 0 and _SCHEDULE_FIELDS & set(cmd.changes):
                raise Conflict(
                    "No se puede cambiar el horario ni el ponente de una sesión con inscritos"
                )

            values: dict[str, Any] = {
                "speaker_id": session.speaker_id,
                "title": session.title,
                "description": session.description,
                "start_at": session.start_at,
                "end_at": session.end_at,
                "capacity": session.capacity,
                **cmd.changes,
            }
            speaker = await _require_speaker(uow, values["speaker_id"])
            data = validate_session_data(
                SessionData(**values), event, min_capacity=max(1, session.registered_count)
            )
            if await uow.sessions.speaker_has_overlap(
                speaker.id, data.start_at, data.end_at, session.id
            ):
                raise ScheduleConflict("El ponente ya tiene una sesión en ese horario")

            session.speaker_id = speaker.id
            session.title = data.title
            session.description = data.description
            session.start_at = data.start_at
            session.end_at = data.end_at
            session.capacity = data.capacity
            await uow.sessions.update(session)
            await uow.commit()
        await self._sync.counts_changed()
        return SessionView(session=session, speaker=speaker)


class DeleteSessionUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def execute(self, cmd: SessionActionCommand) -> None:
        async with self._uow_factory() as uow:
            session = await _load_session(uow, cmd.session_id)
            event = await load_managed_event(uow, session.event_id, cmd.actor)
            ensure_editable(event, self._clock.now())
            if session.registered_count > 0:
                raise Conflict("La sesión tiene inscritos")
            await uow.sessions.delete(session.id)
            await uow.commit()
        await self._sync.counts_changed()


class ListEventSessionsUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListEventSessionsQuery) -> list[SessionView]:
        async with self._uow_factory() as uow:
            event = await load_visible_event(uow, query.event_id, query.viewer)
            sessions = await uow.sessions.list_for_event(event.id)
            speakers = {
                s.id: s
                for s in await uow.speakers.get_many(
                    sorted({s.speaker_id for s in sessions}, key=str)
                )
            }
        ordered = sorted(sessions, key=lambda s: (s.start_at, s.id))
        return [SessionView(session=s, speaker=speakers.get(s.speaker_id)) for s in ordered]
