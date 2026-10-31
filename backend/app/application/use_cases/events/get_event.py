from app.application.dto.queries import GetEventQuery
from app.application.ports.outbound.cache import Cache
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_codec import decode_event, encode_event
from app.application.services.event_sync import EVENTS_CACHE_GROUP
from app.application.use_cases.events._access import load_visible_event
from app.domain.models.event import Event, EventStatus


class GetEventUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, cache: Cache, cache_ttl_seconds: int
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._cache = cache
        self._ttl = cache_ttl_seconds

    async def execute(self, query: GetEventQuery) -> Event:
        key = f"event:{query.event_id}"
        lookup = await self._cache.get(EVENTS_CACHE_GROUP, key)
        if lookup.value is not None:
            # Solo se cachean eventos públicos, por eso un acierto no requiere revisar permisos.
            return decode_event(lookup.value).with_effective_status(self._clock.now())

        async with self._uow_factory() as uow:
            event = await load_visible_event(uow, query.event_id, query.viewer)
        if event.status is not EventStatus.DRAFT:
            await self._cache.set(
                EVENTS_CACHE_GROUP, key, lookup.version, encode_event(event), self._ttl
            )
        return event.with_effective_status(self._clock.now())
