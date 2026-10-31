from app.application.dto.paging import resolve_page
from app.application.dto.queries import EventSearchCriteria, SearchEventsQuery
from app.application.dto.read_models import Page
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import ValidationFailed
from app.domain.models.event import Event, EventStatus

Q_MAX_LENGTH = 100


class SearchEventsUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

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
        return Page(
            items=[e.with_effective_status(now) for e in events],
            total=total,
            page=page,
            page_size=query.page_size,
        )
