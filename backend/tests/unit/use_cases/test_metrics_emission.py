from datetime import timedelta

import pytest

from app.application.dto.commands import EventActionCommand
from app.application.dto.queries import GetEventQuery, SearchEventsQuery
from app.application.services.event_sync import EventSync
from app.application.use_cases.events.change_event_status import (
    CancelEventUseCase,
    FinishEventUseCase,
    PublishEventUseCase,
)
from app.application.use_cases.events.get_event import GetEventUseCase
from app.application.use_cases.events.maintenance import FinishExpiredEventsUseCase
from app.application.use_cases.events.search_events import SearchEventsUseCase
from app.application.use_cases.registrations.event_registrations import RegisterToEventUseCase
from app.domain.models.event import EventStatus
from app.domain.models.user import Role
from tests.factories import make_event, make_user
from tests.fakes.in_memory import (
    FakeCache,
    FakeMetrics,
    FakeSlotCounter,
    FixedClock,
    InMemoryUnitOfWork,
    make_stores,
)


@pytest.fixture
def stores():
    return make_stores()


@pytest.fixture
def metrics():
    return FakeMetrics()


@pytest.fixture
def slots():
    return FakeSlotCounter()


@pytest.fixture
def parts(stores, slots):
    cache = FakeCache()
    return {
        "uow_factory": lambda: InMemoryUnitOfWork(stores),
        "clock": FixedClock(),
        "cache": cache,
        "slots": slots,
        "sync": EventSync(cache, slots),
    }


@pytest.fixture
def register(parts, metrics):
    return RegisterToEventUseCase(
        parts["uow_factory"], parts["clock"], parts["slots"], parts["sync"], metrics
    )


def _event(stores, **kw):
    organizer = make_user(Role.ORGANIZER)
    stores.users[organizer.id] = organizer
    event = make_event(organizer.id, status=kw.pop("status", EventStatus.PUBLISHED), **kw)
    stores.events[event.id] = event
    return organizer, event


def _user(stores):
    user = make_user()
    stores.users[user.id] = user
    return user


class TestRegistrationMetrics:
    async def test_success_is_counted_with_the_slot_filter_decision(
        self, register, metrics, stores
    ):
        _, event = _event(stores, capacity=3)
        await register.execute(EventActionCommand(_user(stores), event.id))

        assert metrics.count("registration_attempt", "ok") == 1
        assert metrics.count("slot_filter", "allowed") == 1

    async def test_each_failure_kind_has_its_own_result(self, register, metrics, stores, slots):
        organizer, event = _event(stores, capacity=1)
        first, second = _user(stores), _user(stores)
        await register.execute(EventActionCommand(first, event.id))

        with pytest.raises(Exception, match="cupos"):
            await register.execute(EventActionCommand(second, event.id))  # lleno
        with pytest.raises(Exception, match="inscripción"):
            await register.execute(EventActionCommand(first, event.id))  # duplicado
        _, closed = _event(stores, status=EventStatus.FINISHED)
        with pytest.raises(Exception, match="no admite"):
            await register.execute(EventActionCommand(second, closed.id))  # cerrado

        assert metrics.count("registration_attempt", "ok") == 1
        assert metrics.count("registration_attempt", "full") == 1
        assert metrics.count("registration_attempt", "duplicate") == 1
        assert metrics.count("registration_attempt", "rejected") == 1

    async def test_filter_rejection_and_duplicate_claims_are_distinguished(
        self, register, metrics, stores, slots
    ):
        _, event = _event(stores, capacity=1)
        user = _user(stores)
        await register.execute(EventActionCommand(user, event.id))
        with pytest.raises(Exception):  # noqa: B017,PT011
            await register.execute(EventActionCommand(user, event.id))
        with pytest.raises(Exception):  # noqa: B017,PT011
            await register.execute(EventActionCommand(_user(stores), event.id))

        assert metrics.count("slot_filter", "duplicate_claim") == 1
        assert metrics.count("slot_filter", "rejected") == 1

    async def test_redis_down_is_reported_as_bypassed(self, parts, metrics, stores):
        down = FakeSlotCounter(available=False)
        register = RegisterToEventUseCase(
            parts["uow_factory"], parts["clock"], down, EventSync(parts["cache"], down), metrics
        )
        _, event = _event(stores)
        await register.execute(EventActionCommand(_user(stores), event.id))

        assert metrics.count("slot_filter", "bypassed") == 1

    async def test_returning_a_slot_after_postgres_rejects_is_counted(
        self, register, metrics, stores, slots
    ):
        _, event = _event(stores, capacity=2, registered=2)
        slots.counters[event.id] = 5  # el contador está desviado: cree que hay cupo
        with pytest.raises(Exception, match="cupos"):
            await register.execute(EventActionCommand(_user(stores), event.id))

        assert metrics.count("slot_compensation") == 1
        assert metrics.count("registration_attempt", "full") == 1

    async def test_unexpected_errors_are_counted_as_error(self, parts, metrics, stores):
        class Boom:
            async def claim(self, *_):
                raise RuntimeError("redis explotó")

        register = RegisterToEventUseCase(
            parts["uow_factory"], parts["clock"], Boom(), parts["sync"], metrics
        )
        _, event = _event(stores)
        with pytest.raises(RuntimeError):
            await register.execute(EventActionCommand(_user(stores), event.id))

        assert metrics.count("registration_attempt", "error") == 1


class TestEventLifecycleMetrics:
    async def test_manual_finish_and_cancel_count_as_manual_closings(self, parts, metrics, stores):
        organizer, finishing = _event(stores)
        _, cancelling = _event(stores)
        stores.events[cancelling.id].organizer_id = organizer.id
        args = (parts["uow_factory"], parts["clock"], parts["sync"], metrics)

        await FinishEventUseCase(*args).execute(EventActionCommand(organizer, finishing.id))
        await CancelEventUseCase(*args).execute(EventActionCommand(organizer, cancelling.id))

        assert metrics.count("event_closed", "manual") == 2
        assert metrics.count("event_closed", "scheduler") == 0

    async def test_publishing_is_not_a_closing(self, parts, metrics, stores):
        organizer, draft = _event(stores, status=EventStatus.DRAFT)
        await PublishEventUseCase(
            parts["uow_factory"], parts["clock"], parts["sync"], metrics
        ).execute(EventActionCommand(organizer, draft.id))

        assert metrics.count("event_closed") == 0

    async def test_the_scheduler_reports_how_many_events_it_closed(self, parts, metrics, stores):
        for _ in range(3):
            _event(stores, starts_in=-timedelta(days=2))
        _event(stores)  # vigente: no se cierra

        closed = await FinishExpiredEventsUseCase(
            parts["uow_factory"], parts["clock"], parts["slots"], parts["sync"], metrics
        ).execute()

        assert len(closed) == 3
        assert metrics.count("event_closed", "scheduler") == 3

    async def test_nothing_to_close_emits_nothing(self, parts, metrics, stores):
        await FinishExpiredEventsUseCase(
            parts["uow_factory"], parts["clock"], parts["slots"], parts["sync"], metrics
        ).execute()
        assert metrics.count("event_closed") == 0


class TestCacheMetrics:
    async def test_event_lookups_report_miss_then_hit(self, parts, metrics, stores):
        _, event = _event(stores)
        get = GetEventUseCase(parts["uow_factory"], parts["clock"], parts["cache"], 60, metrics)

        await get.execute(GetEventQuery(None, event.id))
        await get.execute(GetEventQuery(None, event.id))

        assert [c for c in metrics.calls if c[0] == "cache_lookup"] == [
            ("cache_lookup", ("event", False)),
            ("cache_lookup", ("event", True)),
        ]

    async def test_search_lookups_are_reported_but_personal_listings_are_not(
        self, parts, metrics, stores
    ):
        organizer, _ = _event(stores)
        search = SearchEventsUseCase(
            parts["uow_factory"], parts["clock"], parts["cache"], 60, metrics
        )

        await search.execute(SearchEventsQuery(None))
        await search.execute(SearchEventsQuery(None))
        await search.execute(SearchEventsQuery(organizer, mine=True))  # no pasa por la caché

        assert metrics.count("cache_lookup", "search", False) == 1
        assert metrics.count("cache_lookup", "search", True) == 1
        assert metrics.count("cache_lookup") == 2
