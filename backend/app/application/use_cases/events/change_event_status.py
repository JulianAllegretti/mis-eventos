from app.application.dto.commands import EventActionCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.events._access import load_managed_event
from app.domain.models.event import Event
from app.domain.services import event_lifecycle


class PublishEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: EventActionCommand) -> Event:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            event_lifecycle.publish(event, now)
            await uow.events.update(event)
            await uow.commit()
        return event


class FinishEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: EventActionCommand) -> Event:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            event_lifecycle.finish(event, cmd.actor.id, now)
            await uow.events.update(event)
            await uow.commit()
        return event


class CancelEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: EventActionCommand) -> Event:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            event_lifecycle.cancel(event, cmd.actor.id, now)
            await uow.events.update(event)
            await uow.commit()
        return event
