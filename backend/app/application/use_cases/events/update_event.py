from app.application.dto.commands import UpdateEventCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.events._access import load_managed_event
from app.domain.errors import ValidationFailed
from app.domain.models.event import Event
from app.domain.services.event_lifecycle import ensure_editable
from app.domain.services.event_rules import EventData, validate_event_data

_UPDATABLE = frozenset({"name", "description", "location", "start_at", "end_at", "capacity"})
_NOT_NULLABLE = _UPDATABLE - {"description"}


class UpdateEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, cmd: UpdateEventCommand) -> Event:
        unknown = set(cmd.changes) - _UPDATABLE
        if unknown:
            raise ValidationFailed("Campos no editables", sorted(unknown))
        nulls = sorted(k for k in _NOT_NULLABLE if k in cmd.changes and cmd.changes[k] is None)
        if nulls:
            raise ValidationFailed("Campos que no admiten nulo", nulls)

        now = self._clock.now()
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            ensure_editable(event, now)

            current = EventData(
                name=event.name,
                description=event.description,
                location=event.location,
                start_at=event.start_at,
                end_at=event.end_at,
                capacity=event.capacity,
            )
            merged = EventData(**{**_as_dict(current), **cmd.changes})
            data = validate_event_data(
                merged,
                now=now,
                require_future_start=False,
                min_capacity=max(1, event.registered_count),
            )

            event.name = data.name
            event.description = data.description
            event.location = data.location
            event.start_at = data.start_at
            event.end_at = data.end_at
            event.capacity = data.capacity
            event.updated_at = now
            await uow.events.update(event)
            await uow.commit()
        return event.with_effective_status(now)


def _as_dict(data: EventData) -> dict[str, object]:
    return {name: getattr(data, name) for name in EventData.__slots__}
