from datetime import timedelta

import pytest

from app.application.dto.commands import EventActionCommand, UpdateEventCommand
from app.application.dto.queries import GetEventQuery, SearchEventsQuery
from app.application.services.event_sync import EventSync
from app.application.use_cases.events.get_event import GetEventUseCase
from app.application.use_cases.events.maintenance import (
    FinishExpiredEventsUseCase,
    ReconcileSlotsUseCase,
)
from app.application.use_cases.events.search_events import SearchEventsUseCase
from app.application.use_cases.events.update_event import UpdateEventUseCase
from app.application.use_cases.registrations.event_registrations import RegisterToEventUseCase
from app.domain.models.event import ClosedSource, EventStatus
from app.domain.models.user import Role
from tests.factories import make_event, make_user
from tests.fakes.in_memory import (
    FakeCache,
    FakeSlotCounter,
    FixedClock,
    InMemoryUnitOfWork,
    make_stores,
)


@pytest.fixture
def stores():
    return make_stores()


@pytest.fixture
def uow_factory(stores):
    return lambda: InMemoryUnitOfWork(stores)


@pytest.fixture
def clock():
    return FixedClock()


@pytest.fixture
def cache():
    return FakeCache()


@pytest.fixture
def slots():
    return FakeSlotCounter()


@pytest.fixture
def sync(cache, slots):
    return EventSync(cache, slots)


@pytest.fixture
def owner(stores):
    user = make_user(Role.ORGANIZER)
    stores.users[user.id] = user
    return user


def _published(stores, owner, **kw):
    event = make_event(owner.id, status=EventStatus.PUBLISHED, **kw)
    stores.events[event.id] = event
    return event


class TestReadCache:
    async def test_public_event_is_cached_and_drafts_are_not(
        self, uow_factory, clock, cache, stores, owner
    ):
        get = GetEventUseCase(uow_factory, clock, cache, 60)
        public = _published(stores, owner)
        draft = make_event(owner.id)
        stores.events[draft.id] = draft

        await get.execute(GetEventQuery(None, public.id))
        await get.execute(GetEventQuery(None, public.id))
        await get.execute(GetEventQuery(owner, draft.id))
        await get.execute(GetEventQuery(owner, draft.id))

        assert cache.hits == 1  # solo el segundo acceso al público
        assert not any("event:" + str(draft.id) in key for _, _, key in cache.values)

    async def test_cached_event_still_reports_the_effective_status(
        self, uow_factory, clock, cache, stores, owner
    ):
        get = GetEventUseCase(uow_factory, clock, cache, 60)
        event = _published(stores, owner, starts_in=timedelta(hours=1), lasts=timedelta(hours=2))
        assert (await get.execute(GetEventQuery(None, event.id))).status is EventStatus.PUBLISHED

        clock.advance(timedelta(hours=4))  # el evento terminó, pero sigue en caché

        assert (await get.execute(GetEventQuery(None, event.id))).status is EventStatus.FINISHED
        assert cache.hits == 1

    async def test_search_is_cached_per_query_and_never_for_mine(
        self, uow_factory, clock, cache, stores, owner
    ):
        search = SearchEventsUseCase(uow_factory, clock, cache, 60)
        _published(stores, owner, name="Python")
        _published(stores, owner, name="Rust")

        first = await search.execute(SearchEventsQuery(None, q="py"))
        again = await search.execute(SearchEventsQuery(None, q="py"))
        other = await search.execute(SearchEventsQuery(None, q="rust"))
        await search.execute(SearchEventsQuery(owner, mine=True))
        await search.execute(SearchEventsQuery(owner, mine=True))

        assert [e.name for e in first.items] == [e.name for e in again.items] == ["Python"]
        assert [e.name for e in other.items] == ["Rust"]
        assert cache.hits == 1  # solo el segundo "py"

    async def test_writes_invalidate_the_cache(
        self, uow_factory, clock, cache, sync, stores, owner
    ):
        get = GetEventUseCase(uow_factory, clock, cache, 60)
        event = _published(stores, owner, name="Original")
        await get.execute(GetEventQuery(None, event.id))  # llena la caché

        await UpdateEventUseCase(uow_factory, clock, sync).execute(
            UpdateEventCommand(owner, event.id, {"name": "Cambiado"})
        )

        assert (await get.execute(GetEventQuery(None, event.id))).name == "Cambiado"

    async def test_registrations_refresh_the_displayed_slots(
        self, uow_factory, clock, cache, sync, slots, stores, owner
    ):
        get = GetEventUseCase(uow_factory, clock, cache, 60)
        register = RegisterToEventUseCase(uow_factory, clock, slots, sync)
        event = _published(stores, owner, capacity=5)
        assert (await get.execute(GetEventQuery(None, event.id))).registered_count == 0

        member = make_user()
        stores.users[member.id] = member
        await register.execute(EventActionCommand(member, event.id))

        assert (await get.execute(GetEventQuery(None, event.id))).registered_count == 1

    async def test_value_computed_before_an_invalidation_is_not_published(self, cache):
        stale = await cache.get("events", "k")  # lectura con la versión 0
        await cache.invalidate_group("events")  # otro escritor invalida
        await cache.set("events", "k", stale.version, "viejo", 60)

        assert (await cache.get("events", "k")).value is None


class TestFinishExpiredEvents:
    async def test_closes_only_expired_published_events_as_scheduler(
        self, uow_factory, clock, slots, sync, stores, owner
    ):
        expired = _published(stores, owner, starts_in=-timedelta(days=2))
        running = _published(stores, owner, starts_in=-timedelta(hours=1), lasts=timedelta(hours=5))
        upcoming = _published(stores, owner)
        draft = make_event(owner.id, starts_in=-timedelta(days=2))
        stores.events[draft.id] = draft
        slots.counters[expired.id] = 3

        closed = await FinishExpiredEventsUseCase(uow_factory, clock, slots, sync).execute()

        assert closed == [expired.id]
        assert expired.status is EventStatus.FINISHED
        assert expired.closed_source is ClosedSource.SCHEDULER
        assert expired.closed_by_id is None
        assert expired.closed_at == clock.now()
        assert (running.status, upcoming.status, draft.status) == (
            EventStatus.PUBLISHED,
            EventStatus.PUBLISHED,
            EventStatus.DRAFT,
        )
        assert expired.id not in slots.counters  # el contador se descartó

    async def test_is_idempotent_and_invalidates_cache_once(
        self, uow_factory, clock, slots, sync, cache, stores, owner
    ):
        _published(stores, owner, starts_in=-timedelta(days=2))
        job = FinishExpiredEventsUseCase(uow_factory, clock, slots, sync)

        assert len(await job.execute()) == 1
        assert await job.execute() == []
        assert cache.versions["events"] == 1

    async def test_manual_closing_keeps_its_own_trace(
        self, uow_factory, clock, slots, sync, stores, owner
    ):
        event = _published(stores, owner, starts_in=-timedelta(days=2))
        event.status = EventStatus.FINISHED
        event.closed_at, event.closed_by_id = clock.now(), owner.id
        event.closed_source = ClosedSource.MANUAL

        assert await FinishExpiredEventsUseCase(uow_factory, clock, slots, sync).execute() == []
        assert event.closed_source is ClosedSource.MANUAL


class TestReconcileSlots:
    async def test_fixes_drifted_counters_but_never_creates_them(
        self, uow_factory, clock, slots, stores, owner
    ):
        drifted = _published(stores, owner, capacity=10, registered=4)
        untouched = _published(stores, owner, capacity=10)
        slots.counters[drifted.id] = 9  # debería ser 6

        checked = await ReconcileSlotsUseCase(uow_factory, clock, slots).execute()

        assert checked == 2
        assert slots.counters[drifted.id] == 6
        assert untouched.id not in slots.counters

    async def test_ignores_drafts_and_expired_events(
        self, uow_factory, clock, slots, stores, owner
    ):
        draft = make_event(owner.id)
        stores.events[draft.id] = draft
        _published(stores, owner, starts_in=-timedelta(days=3))

        assert await ReconcileSlotsUseCase(uow_factory, clock, slots).execute() == 0
