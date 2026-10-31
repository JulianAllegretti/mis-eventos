import hashlib
from datetime import datetime

from app.application.dto.paging import resolve_page
from app.application.dto.queries import EventSearchCriteria, SearchEventsQuery
from app.application.dto.read_models import Page
from app.application.ports.outbound.cache import Cache
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_codec import decode_page, encode_page
from app.application.services.event_sync import EVENTS_CACHE_GROUP
from app.domain.errors import ValidationFailed
from app.domain.models.event import Event, EventStatus

Q_MAX_LENGTH = 100


class SearchEventsUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, cache: Cache, cache_ttl_seconds: int
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._cache = cache
        self._ttl = cache_ttl_seconds

    async def execute(self, query: SearchEventsQuery) -> Page[Event]:
        page, limit, offset = resolve_page(query.page, query.page_size)
        q = query.q.strip() if query.q else None
        if q and len(q) > Q_MAX_LENGTH:
            raise ValidationFailed(f"q: máximo {Q_MAX_LENGTH} caracteres")
        if query.mine and query.viewer is None:
            raise ValidationFailed("scope=mine requiere una sesión")
        if query.status is EventStatus.DRAFT and not query.mine:
            raise ValidationFailed("Los borradores solo se consultan con scope=mine")

        now = self._clock.now()
        # Solo el listado público es cacheable: no depende de quién consulta ni incluye borradores.
        cache_key = None if query.mine else self._cache_key(q, query.status, page, query.page_size)
        version = ""
        if cache_key is not None:
            lookup = await self._cache.get(EVENTS_CACHE_GROUP, cache_key)
            version = lookup.version
            if lookup.value is not None:
                return self._with_effective_status(decode_page(lookup.value), now)

        criteria = EventSearchCriteria(
            now=now,
            q=q or None,
            status=query.status,
            organizer_id=query.viewer.id if query.mine and query.viewer else None,
            exclude_drafts=not query.mine,
            limit=limit,
            offset=offset,
        )
        async with self._uow_factory() as uow:
            events, total = await uow.events.search(criteria)
        result = Page(items=events, total=total, page=page, page_size=query.page_size)
        if cache_key is not None:
            await self._cache.set(
                EVENTS_CACHE_GROUP, cache_key, version, encode_page(result), self._ttl
            )
        return self._with_effective_status(result, now)

    @staticmethod
    def _cache_key(q: str | None, status: EventStatus | None, page: int, page_size: int) -> str:
        raw = f"{q or ''}|{status.value if status else ''}|{page}|{page_size}"
        return "search:" + hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def _with_effective_status(page: Page[Event], now: datetime) -> Page[Event]:
        return Page(
            items=[e.with_effective_status(now) for e in page.items],
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
