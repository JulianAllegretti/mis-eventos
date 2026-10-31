from uuid import UUID

from app.application.dto.commands import EventActionCommand
from app.application.dto.paging import resolve_page
from app.application.dto.queries import ListAttendeesQuery, ListMyRegistrationsQuery
from app.application.dto.read_models import AttendeeView, MyRegistration, Page, SessionView
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.slot_counter import SlotCounter, SlotResult
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_sync import EventSync
from app.application.use_cases.events._access import load_managed_event
from app.domain.errors import AlreadyRegistered, EventFull, NotFound
from app.domain.models.registration import Registration
from app.domain.services.permissions import can_view_event
from app.domain.services.scheduling import ensure_registrable


class RegisterToEventUseCase:
    """Inscripción a un evento con control de concurrencia (ADR 0005).

    1. El contador de Redis rechaza rápido cuando no hay cupo.
    2. PostgreSQL decide: restricción única por (usuario, evento) y actualización condicional
       del contador `registered_count`. Si algo falla, se devuelve el cupo a Redis.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, slots: SlotCounter, sync: EventSync
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._slots = slots
        self._sync = sync

    async def execute(self, cmd: EventActionCommand) -> Registration:
        # 1) Colapsa los clics dobles antes de reservar cupo (ver SlotCounter.claim).
        if not await self._slots.claim(cmd.event_id, cmd.actor.id):
            raise AlreadyRegistered("Ya tienes una inscripción en curso para este evento")
        try:
            registration = await self._reserve_and_persist(cmd)
        except AlreadyRegistered:
            raise  # el candado se conserva: el usuario ya está inscrito
        except BaseException:
            await self._slots.unclaim(cmd.event_id, cmd.actor.id)  # permite reintentar de inmediato
            raise
        await self._sync.counts_changed()
        return registration

    async def _reserve_and_persist(self, cmd: EventActionCommand) -> Registration:
        holds_slot = await self._acquire_slot(cmd)
        try:
            return await self._persist(cmd)
        except BaseException:
            if holds_slot:
                await self._slots.release(cmd.event_id)
            raise

    async def _acquire_slot(self, cmd: EventActionCommand) -> bool:
        """True si se descontó un cupo del contador (y por tanto hay que devolverlo si falla)."""
        result = await self._slots.try_acquire(cmd.event_id)
        if result is SlotResult.MISSING:
            await self._slots.initialize(cmd.event_id, await self._available_slots(cmd))
            result = await self._slots.try_acquire(cmd.event_id)
        if result is SlotResult.FULL:
            raise EventFull()
        return result is SlotResult.ALLOWED

    async def _available_slots(self, cmd: EventActionCommand) -> int:
        async with self._uow_factory() as uow:
            event = await uow.events.get(cmd.event_id)
            if event is None or not can_view_event(cmd.actor, event):
                raise NotFound("Evento no encontrado")
            ensure_registrable(event, self._clock.now())
            return event.available_slots

    async def _persist(self, cmd: EventActionCommand) -> Registration:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await uow.events.get(cmd.event_id)
            if event is None or not can_view_event(cmd.actor, event):
                raise NotFound("Evento no encontrado")
            ensure_registrable(event, now)

            registration = Registration.new(user_id=cmd.actor.id, event_id=event.id, now=now)
            await uow.registrations.add(registration)  # AlreadyRegistered si ya está inscrito
            if not await uow.events.try_increment_registered(event.id, now):
                raise EventFull()
            await uow.commit()
        return registration


class CancelEventRegistrationUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, slots: SlotCounter, sync: EventSync
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._slots = slots
        self._sync = sync

    async def execute(self, cmd: EventActionCommand) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await uow.events.get(cmd.event_id)
            if event is None or not can_view_event(cmd.actor, event):
                raise NotFound("Evento no encontrado")
            ensure_registrable(event, now)

            if not await uow.registrations.cancel(cmd.actor.id, event.id, now):
                raise NotFound("No tienes una inscripción activa en este evento")
            session_ids = await uow.session_registrations.cancel_all_for_event(
                cmd.actor.id, event.id, now
            )
            for session_id in session_ids:
                await uow.sessions.decrement_registered(session_id)
            await uow.events.decrement_registered(event.id)
            await uow.commit()
        await self._slots.release(cmd.event_id)
        await self._slots.unclaim(cmd.event_id, cmd.actor.id)
        await self._sync.counts_changed()


class ListMyRegistrationsUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListMyRegistrationsQuery) -> list[MyRegistration]:
        async with self._uow_factory() as uow:
            registrations = await uow.registrations.list_active_for_user(query.user.id)
            session_regs = await uow.session_registrations.list_active_for_user(query.user.id)
            speaker_ids = sorted({s.speaker_id for _, s in session_regs}, key=str)
            speakers = {sp.id: sp for sp in await uow.speakers.get_many(speaker_ids)}

        sessions_by_event: dict[UUID, list[SessionView]] = {}
        for _, session in sorted(session_regs, key=lambda pair: (pair[1].start_at, pair[1].id)):
            sessions_by_event.setdefault(session.event_id, []).append(
                SessionView(session=session, speaker=speakers.get(session.speaker_id))
            )
        return [
            MyRegistration(
                event=event,
                registered_at=registration.created_at,
                sessions=sessions_by_event.get(event.id, []),
            )
            for registration, event in registrations
        ]


class ListEventAttendeesUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListAttendeesQuery) -> Page[AttendeeView]:
        page, limit, offset = resolve_page(query.page, query.page_size)
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, query.event_id, query.actor)
            rows, total = await uow.registrations.list_attendees(event.id, limit, offset)
        return Page(
            items=[AttendeeView(registration=r, user=u) for r, u in rows],
            total=total,
            page=page,
            page_size=query.page_size,
        )
