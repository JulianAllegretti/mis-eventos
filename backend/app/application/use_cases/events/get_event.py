from app.application.dto.queries import GetEventQuery
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.events._access import load_visible_event
from app.domain.models.event import Event


class GetEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, query: GetEventQuery) -> Event:
        async with self._uow_factory() as uow:
            event = await load_visible_event(uow, query.event_id, query.viewer)
        return event.with_effective_status(self._clock.now())
