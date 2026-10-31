from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.dto.commands import EventActionCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_sync import EventSync
from app.application.use_cases.events._access import load_managed_event
from app.domain.models.event import Event
from app.domain.services import event_lifecycle

Transition = Callable[[Event, UUID, datetime], None]


class _ChangeStatus:
    """Aplica una transición del ciclo de vida, la persiste y sincroniza caché y cupos."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sync = sync

    async def _run(self, cmd: EventActionCommand, transition: Transition) -> Event:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            transition(event, cmd.actor.id, now)
            await uow.events.update(event)
            await uow.commit()
        await self._sync.event_changed(event.id)
        return event


class PublishEventUseCase(_ChangeStatus):
    async def execute(self, cmd: EventActionCommand) -> Event:
        return await self._run(cmd, lambda event, _actor, now: event_lifecycle.publish(event, now))


class FinishEventUseCase(_ChangeStatus):
    async def execute(self, cmd: EventActionCommand) -> Event:
        return await self._run(cmd, event_lifecycle.finish)


class CancelEventUseCase(_ChangeStatus):
    async def execute(self, cmd: EventActionCommand) -> Event:
        return await self._run(cmd, event_lifecycle.cancel)
