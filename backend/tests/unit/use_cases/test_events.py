from datetime import timedelta

import pytest

from app.application.dto.commands import CreateEventCommand, EventActionCommand, UpdateEventCommand
from app.application.dto.queries import GetEventQuery, SearchEventsQuery
from app.application.use_cases.events.change_event_status import (
    CancelEventUseCase,
    FinishEventUseCase,
    PublishEventUseCase,
)
from app.application.use_cases.events.create_event import CreateEventUseCase
from app.application.use_cases.events.delete_event import DeleteEventUseCase
from app.application.use_cases.events.get_event import GetEventUseCase
from app.application.use_cases.events.search_events import SearchEventsUseCase
from app.application.use_cases.events.update_event import UpdateEventUseCase
from app.domain.errors import Conflict, Forbidden, InvalidTransition, NotFound, ValidationFailed
from app.domain.models.event import EventStatus
from app.domain.models.user import Role
from tests.factories import make_event, make_user
from tests.fakes.in_memory import FIXED_NOW, FixedClock, make_uow_factory


@pytest.fixture
def events():
    return {}


@pytest.fixture
def uow_factory(events):
    return make_uow_factory({}, events)


@pytest.fixture
def clock():
    return FixedClock()


def _create_cmd(actor, **overrides):
    base = {
        "name": "Congreso",
        "description": "Desc",
        "location": "Bogotá",
        "start_at": FIXED_NOW + timedelta(days=5),
        "end_at": FIXED_NOW + timedelta(days=5, hours=4),
        "capacity": 30,
    }
    return CreateEventCommand(actor=actor, **{**base, **overrides})


class TestCreateEvent:
    async def test_organizer_creates_a_draft_owned_by_them(self, uow_factory, clock, events):
        organizer = make_user(Role.ORGANIZER)
        event = await CreateEventUseCase(uow_factory, clock).execute(_create_cmd(organizer))

        assert event.status is EventStatus.DRAFT
        assert event.organizer_id == organizer.id
        assert event.registered_count == 0
        assert events[event.id] is event

    async def test_attendee_cannot_create(self, uow_factory, clock, events):
        with pytest.raises(Forbidden):
            await CreateEventUseCase(uow_factory, clock).execute(_create_cmd(make_user()))
        assert events == {}

    async def test_start_must_be_in_the_future(self, uow_factory, clock):
        cmd = _create_cmd(
            make_user(Role.ORGANIZER),
            start_at=FIXED_NOW - timedelta(hours=1),
            end_at=FIXED_NOW + timedelta(hours=1),
        )
        with pytest.raises(ValidationFailed):
            await CreateEventUseCase(uow_factory, clock).execute(cmd)


class TestUpdateEvent:
    async def test_owner_updates_only_the_given_fields(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id)
        events[event.id] = event

        updated = await UpdateEventUseCase(uow_factory, clock).execute(
            UpdateEventCommand(actor=owner, event_id=event.id, changes={"name": "  Nuevo  "})
        )

        assert updated.name == "Nuevo"
        assert updated.location == "Bogotá"
        assert updated.capacity == 100

    async def test_description_can_be_cleared_but_name_cannot_be_null(
        self, uow_factory, clock, events
    ):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id)
        events[event.id] = event
        use_case = UpdateEventUseCase(uow_factory, clock)

        cleared = await use_case.execute(UpdateEventCommand(owner, event.id, {"description": None}))
        assert cleared.description is None
        with pytest.raises(ValidationFailed):
            await use_case.execute(UpdateEventCommand(owner, event.id, {"name": None}))

    async def test_rejects_unknown_fields(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id)
        events[event.id] = event
        with pytest.raises(ValidationFailed):
            await UpdateEventUseCase(uow_factory, clock).execute(
                UpdateEventCommand(owner, event.id, {"organizer_id": "x", "registered_count": 0})
            )

    async def test_capacity_cannot_go_below_registered(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id, status=EventStatus.PUBLISHED, capacity=50, registered=20)
        events[event.id] = event
        use_case = UpdateEventUseCase(uow_factory, clock)

        with pytest.raises(ValidationFailed):
            await use_case.execute(UpdateEventCommand(owner, event.id, {"capacity": 19}))
        assert (
            await use_case.execute(UpdateEventCommand(owner, event.id, {"capacity": 20}))
        ).capacity == 20

    async def test_other_organizer_is_forbidden_and_admin_allowed(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id, status=EventStatus.PUBLISHED)
        events[event.id] = event
        use_case = UpdateEventUseCase(uow_factory, clock)
        change = {"location": "Medellín"}

        with pytest.raises(Forbidden):
            await use_case.execute(UpdateEventCommand(make_user(Role.ORGANIZER), event.id, change))
        result = await use_case.execute(UpdateEventCommand(make_user(Role.ADMIN), event.id, change))
        assert result.location == "Medellín"

    async def test_foreign_draft_looks_nonexistent(self, uow_factory, clock, events):
        event = make_event(make_user(Role.ORGANIZER).id)  # borrador de otro
        events[event.id] = event
        with pytest.raises(NotFound):
            await UpdateEventUseCase(uow_factory, clock).execute(
                UpdateEventCommand(make_user(Role.ORGANIZER), event.id, {"name": "X"})
            )

    @pytest.mark.parametrize("status", [EventStatus.FINISHED, EventStatus.CANCELLED])
    async def test_closed_events_are_not_editable(self, uow_factory, clock, events, status):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id, status=status)
        events[event.id] = event
        with pytest.raises(InvalidTransition):
            await UpdateEventUseCase(uow_factory, clock).execute(
                UpdateEventCommand(owner, event.id, {"name": "X"})
            )


class TestGetAndSearch:
    async def test_get_returns_effective_status(self, uow_factory, clock, events):
        event = make_event(
            make_user(Role.ORGANIZER).id, status=EventStatus.PUBLISHED, starts_in=-timedelta(days=3)
        )
        events[event.id] = event

        result = await GetEventUseCase(uow_factory, clock).execute(GetEventQuery(None, event.id))

        assert result.status is EventStatus.FINISHED

    async def test_anonymous_cannot_get_a_draft(self, uow_factory, clock, events):
        event = make_event(make_user(Role.ORGANIZER).id)
        events[event.id] = event
        with pytest.raises(NotFound):
            await GetEventUseCase(uow_factory, clock).execute(GetEventQuery(None, event.id))

    async def test_search_hides_drafts_and_matches_part_of_the_name_ignoring_case(
        self, uow_factory, clock, events
    ):
        owner = make_user(Role.ORGANIZER)
        for name, status in (
            ("Congreso de Python", EventStatus.PUBLISHED),
            ("Taller de PYTHON avanzado", EventStatus.PUBLISHED),
            ("Charla de Rust", EventStatus.PUBLISHED),
            ("Python secreto", EventStatus.DRAFT),
        ):
            event = make_event(owner.id, name=name, status=status)
            events[event.id] = event

        page = await SearchEventsUseCase(uow_factory, clock).execute(
            SearchEventsQuery(viewer=None, q="python")
        )

        assert sorted(e.name for e in page.items) == [
            "Congreso de Python",
            "Taller de PYTHON avanzado",
        ]
        assert page.total == 2

    async def test_mine_includes_own_drafts_only(self, uow_factory, clock, events):
        me, other = make_user(Role.ORGANIZER), make_user(Role.ORGANIZER)
        mine = make_event(me.id, name="Mi borrador")
        theirs = make_event(other.id, name="Borrador ajeno")
        events.update({mine.id: mine, theirs.id: theirs})

        page = await SearchEventsUseCase(uow_factory, clock).execute(
            SearchEventsQuery(viewer=me, mine=True)
        )

        assert [e.name for e in page.items] == ["Mi borrador"]

    async def test_pagination_and_ordering_by_start(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        for days in (3, 1, 2):
            event = make_event(
                owner.id,
                name=f"E{days}",
                status=EventStatus.PUBLISHED,
                starts_in=timedelta(days=days),
            )
            events[event.id] = event
        search = SearchEventsUseCase(uow_factory, clock)

        first = await search.execute(SearchEventsQuery(None, page=1, page_size=2))
        second = await search.execute(SearchEventsQuery(None, page=2, page_size=2))

        assert [e.name for e in first.items] == ["E1", "E2"]
        assert [e.name for e in second.items] == ["E3"]
        assert first.total == second.total == 3

    async def test_status_filter_uses_effective_status(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        expired = make_event(
            owner.id, name="Vencido", status=EventStatus.PUBLISHED, starts_in=-timedelta(days=2)
        )
        live = make_event(owner.id, name="Vigente", status=EventStatus.PUBLISHED)
        events.update({expired.id: expired, live.id: live})
        search = SearchEventsUseCase(uow_factory, clock)

        finished = await search.execute(SearchEventsQuery(None, status=EventStatus.FINISHED))
        published = await search.execute(SearchEventsQuery(None, status=EventStatus.PUBLISHED))

        assert [e.name for e in finished.items] == ["Vencido"]
        assert [e.name for e in published.items] == ["Vigente"]

    @pytest.mark.parametrize(
        "query",
        [
            SearchEventsQuery(None, page=0),
            SearchEventsQuery(None, page_size=51),
            SearchEventsQuery(None, mine=True),
            SearchEventsQuery(None, status=EventStatus.DRAFT),
            SearchEventsQuery(None, q="x" * 101),
        ],
    )
    async def test_invalid_queries_are_rejected(self, uow_factory, clock, query):
        with pytest.raises(ValidationFailed):
            await SearchEventsUseCase(uow_factory, clock).execute(query)


class TestStatusChangesAndDelete:
    async def test_publish_then_finish_then_no_more_changes(self, uow_factory, clock, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id)
        events[event.id] = event
        cmd = EventActionCommand(owner, event.id)

        assert (
            await PublishEventUseCase(uow_factory, clock).execute(cmd)
        ).status is EventStatus.PUBLISHED
        finished = await FinishEventUseCase(uow_factory, clock).execute(cmd)
        assert finished.status is EventStatus.FINISHED
        assert finished.closed_by_id == owner.id
        with pytest.raises(InvalidTransition):
            await CancelEventUseCase(uow_factory, clock).execute(cmd)

    async def test_non_owner_cannot_change_status(self, uow_factory, clock, events):
        event = make_event(make_user(Role.ORGANIZER).id, status=EventStatus.PUBLISHED)
        events[event.id] = event
        with pytest.raises(Forbidden):
            await CancelEventUseCase(uow_factory, clock).execute(
                EventActionCommand(make_user(Role.ORGANIZER), event.id)
            )

    async def test_delete_removes_an_event_without_registrations(self, uow_factory, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id)
        events[event.id] = event
        await DeleteEventUseCase(uow_factory).execute(EventActionCommand(owner, event.id))
        assert events == {}

    async def test_delete_is_refused_when_there_are_registrations(self, uow_factory, events):
        owner = make_user(Role.ORGANIZER)
        event = make_event(owner.id, status=EventStatus.PUBLISHED, registered=3)
        events[event.id] = event
        with pytest.raises(Conflict):
            await DeleteEventUseCase(uow_factory).execute(EventActionCommand(owner, event.id))
        assert event.id in events
