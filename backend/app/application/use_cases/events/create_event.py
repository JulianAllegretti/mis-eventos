from app.application.dto.commands import CreateEventCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.models.event import Event
from app.domain.services.event_rules import EventData, validate_event_data
from app.domain.services.permissions import MANAGERS, ensure_role


class CreateEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: CreateEventCommand) -> Event:
        ensure_role(cmd.actor, *MANAGERS)
        now = self._clock.now()
        data = validate_event_data(
            EventData(
                name=cmd.name,
                description=cmd.description,
                location=cmd.location,
                start_at=cmd.start_at,
                end_at=cmd.end_at,
                capacity=cmd.capacity,
            ),
            now=now,
            require_future_start=True,
        )
        event = Event.new(
            name=data.name,
            description=data.description,
            location=data.location,
            start_at=data.start_at,
            end_at=data.end_at,
            capacity=data.capacity,
            organizer_id=cmd.actor.id,
            now=now,
        )
        async with self._uow_factory() as uow:
            await uow.events.add(event)
            await uow.commit()
        return event
