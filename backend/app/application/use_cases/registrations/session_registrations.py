from app.application.dto.commands import SessionActionCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.event_sync import EventSync
from app.domain.errors import AlreadyRegistered, Conflict, NotFound, ScheduleConflict, SessionFull
from app.domain.models.event import Event
from app.domain.models.registration import SessionRegistration
from app.domain.models.session import Session
from app.domain.services.permissions import can_view_event
from app.domain.services.scheduling import ensure_registrable


async def _load_session_and_event(
    uow: UnitOfWork, cmd: SessionActionCommand
) -> tuple[Session, Event]:
    session = await uow.sessions.get(cmd.session_id)
    if session is None:
        raise NotFound("Sesión no encontrada")
    event = await uow.events.get(session.event_id)
    if event is None or not can_view_event(cmd.actor, event):
        raise NotFound("Sesión no encontrada")
    return session, event


class RegisterToSessionUseCase:
    """Inscripción a una sesión: exige estar inscrito al evento, cupo y ausencia de solapes."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def execute(self, cmd: SessionActionCommand) -> SessionRegistration:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            session, event = await _load_session_and_event(uow, cmd)
            ensure_registrable(event, now)
            if await uow.registrations.get_active(cmd.actor.id, event.id) is None:
                raise Conflict("Primero debes inscribirte al evento")

            # Serializa las inscripciones del mismo usuario: evita que dos clics simultáneos
            # a sesiones solapadas pasen ambos la validación.
            await uow.session_registrations.lock_user(cmd.actor.id)
            if await uow.session_registrations.get_active(cmd.actor.id, session.id) is not None:
                raise AlreadyRegistered("Ya estás inscrito en esta sesión")
            if await uow.session_registrations.has_overlap(
                cmd.actor.id, session.start_at, session.end_at
            ):
                raise ScheduleConflict("Ya estás inscrito en otra sesión en ese horario")

            registration = SessionRegistration.new(
                user_id=cmd.actor.id, session_id=session.id, now=now
            )
            await uow.session_registrations.add(registration)
            if not await uow.sessions.try_increment_registered(session.id):
                raise SessionFull()
            await uow.commit()
        await self._sync.counts_changed()
        return registration


class CancelSessionRegistrationUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def execute(self, cmd: SessionActionCommand) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            session, event = await _load_session_and_event(uow, cmd)
            ensure_registrable(event, now)
            if not await uow.session_registrations.cancel(cmd.actor.id, session.id, now):
                raise NotFound("No tienes una inscripción activa en esta sesión")
            await uow.sessions.decrement_registered(session.id)
            await uow.commit()
        await self._sync.counts_changed()
