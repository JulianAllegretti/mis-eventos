from uuid import UUID

from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.slot_counter import SlotCounter
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_sync import EventSync


class FinishExpiredEventsUseCase:
    """Cierre automático (ADR 0008): publicados vencidos → finished (source=scheduler)."""

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, slots: SlotCounter, sync: EventSync
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._slots = slots
        self._sync = sync

    async def execute(self) -> list[UUID]:
        async with self._uow_factory() as uow:
            closed = await uow.events.finish_expired(self._clock.now())
            await uow.commit()
        for event_id in closed:
            await self._slots.invalidate(event_id)
        if closed:
            await self._sync.counts_changed()
        return closed


class ReconcileSlotsUseCase:
    """Corrige desvíos del contador de Redis tomando como verdad a PostgreSQL (ADR 0005)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, slots: SlotCounter) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._slots = slots

    async def execute(self) -> int:
        async with self._uow_factory() as uow:
            availability = await uow.events.list_open_availability(self._clock.now())
        for event_id, available in availability:
            await self._slots.reconcile(event_id, available)
        return len(availability)
