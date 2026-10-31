from datetime import timedelta

import pytest

from app.application.dto.commands import EventActionCommand, SessionActionCommand
from app.application.dto.queries import ListAttendeesQuery, ListMyRegistrationsQuery
from app.application.services.event_sync import EventSync
from app.application.use_cases.registrations.event_registrations import (
    CancelEventRegistrationUseCase,
    ListEventAttendeesUseCase,
    ListMyRegistrationsUseCase,
    RegisterToEventUseCase,
)
from app.application.use_cases.registrations.session_registrations import (
    CancelSessionRegistrationUseCase,
    RegisterToSessionUseCase,
)
from app.domain.errors import (
    AlreadyRegistered,
    Conflict,
    EventFull,
    Forbidden,
    InvalidTransition,
    NotFound,
    ScheduleConflict,
    SessionFull,
)
from app.domain.models.event import EventStatus
from app.domain.models.session import Session
from app.domain.models.user import Role
from tests.factories import make_event, make_speaker, make_user
from tests.fakes.in_memory import (
    FIXED_NOW,
    FakeCache,
    FakeSlotCounter,
    FixedClock,
    InMemoryUnitOfWork,
    make_stores,
)

EVENT_START = FIXED_NOW + timedelta(days=10)


@pytest.fixture
def stores():
    return make_stores()


@pytest.fixture
def uow_factory(stores):
    return lambda: InMemoryUnitOfWork(stores)


@pytest.fixture
def slots():
    return FakeSlotCounter()


@pytest.fixture
def cache():
    return FakeCache()


@pytest.fixture
def sync(cache, slots):
    return EventSync(cache, slots)


@pytest.fixture
def register(uow_factory, slots, sync):
    return RegisterToEventUseCase(uow_factory, FixedClock(), slots, sync)


@pytest.fixture
def cancel(uow_factory, slots, sync):
    return CancelEventRegistrationUseCase(uow_factory, FixedClock(), slots, sync)


@pytest.fixture
def organizer(stores):
    user = make_user(Role.ORGANIZER)
    stores.users[user.id] = user
    return user


def _user(stores, role=Role.ATTENDEE):
    user = make_user(role)
    stores.users[user.id] = user
    return user


def _event(stores, organizer, *, capacity=2, registered=0, status=EventStatus.PUBLISHED, **kw):
    event = make_event(organizer.id, status=status, capacity=capacity, registered=registered, **kw)
    stores.events[event.id] = event
    return event


def _session(stores, event, speaker, start_hour, hours=1, capacity=5, registered=0):
    session = Session.new(
        event_id=event.id,
        speaker_id=speaker.id,
        title=f"Sesión {start_hour}h",
        description=None,
        start_at=EVENT_START + timedelta(hours=start_hour),
        end_at=EVENT_START + timedelta(hours=start_hour + hours),
        capacity=capacity,
        now=FIXED_NOW,
    )
    session.registered_count = registered
    stores.sessions[session.id] = session
    return session


class TestRegisterToEvent:
    async def test_registers_and_takes_one_slot_from_both_counters(
        self, register, stores, slots, cache, organizer
    ):
        event, user = _event(stores, organizer, capacity=3), _user(stores)

        registration = await register.execute(EventActionCommand(user, event.id))

        assert registration.user_id == user.id
        assert event.registered_count == 1
        assert slots.counters[event.id] == 2  # se inicializó con 3 y se descontó 1
        assert cache.versions["events"] == 1

    async def test_last_slot_goes_to_one_user_only(self, register, stores, slots, organizer):
        event = _event(stores, organizer, capacity=1)
        first, second = _user(stores), _user(stores)

        await register.execute(EventActionCommand(first, event.id))
        with pytest.raises(EventFull):
            await register.execute(EventActionCommand(second, event.id))

        assert event.registered_count == 1
        assert len(stores.registrations) == 1
        assert slots.counters[event.id] == 0

    async def test_full_counter_rejects_without_touching_the_database(
        self, register, stores, slots, organizer
    ):
        event = _event(stores, organizer, capacity=5)
        slots.counters[event.id] = 0  # Redis dice que no hay cupo

        with pytest.raises(EventFull):
            await register.execute(EventActionCommand(_user(stores), event.id))

        assert event.registered_count == 0
        assert stores.registrations == {}

    async def test_postgres_is_the_authority_when_the_counter_drifts(
        self, register, stores, slots, organizer
    ):
        event = _event(stores, organizer, capacity=2, registered=2)  # PostgreSQL: lleno
        slots.counters[event.id] = 5  # contador desviado: cree que hay cupos

        with pytest.raises(EventFull):
            await register.execute(EventActionCommand(_user(stores), event.id))

        assert event.registered_count == 2
        assert stores.registrations == {}
        assert slots.counters[event.id] == 5  # el cupo descontado se devolvió

    async def test_duplicate_registration_returns_the_slot(
        self, register, stores, slots, organizer
    ):
        event, user = _event(stores, organizer, capacity=3), _user(stores)
        await register.execute(EventActionCommand(user, event.id))

        with pytest.raises(AlreadyRegistered):
            await register.execute(EventActionCommand(user, event.id))

        assert event.registered_count == 1
        assert slots.counters[event.id] == 2  # solo cuenta la primera inscripción

    async def test_a_second_attempt_is_stopped_by_the_claim_before_taking_a_slot(
        self, register, stores, slots, organizer
    ):
        event, user = _event(stores, organizer, capacity=3), _user(stores)
        await slots.claim(event.id, user.id)  # hay un intento en vuelo de este usuario

        with pytest.raises(AlreadyRegistered):
            await register.execute(EventActionCommand(user, event.id))

        assert ("acquire", event.id) not in slots.calls  # ni siquiera se tocó el contador
        assert event.registered_count == 0

    async def test_a_failed_attempt_releases_the_claim_so_the_user_can_retry(
        self, register, stores, slots, organizer
    ):
        event, user = _event(stores, organizer, capacity=1, registered=1), _user(stores)
        with pytest.raises(EventFull):
            await register.execute(EventActionCommand(user, event.id))
        assert (event.id, user.id) not in slots.claims

        event.capacity = 2  # el organizador amplía el cupo...
        await slots.invalidate(event.id)  # ...y UpdateEvent descarta el contador (EventSync)
        await register.execute(EventActionCommand(user, event.id))  # reintento inmediato

        assert event.registered_count == 2

    async def test_works_without_redis(self, uow_factory, stores, organizer, sync):
        down = FakeSlotCounter(available=False)
        use_case = RegisterToEventUseCase(uow_factory, FixedClock(), down, sync)
        event, user = _event(stores, organizer, capacity=1), _user(stores)

        await use_case.execute(EventActionCommand(user, event.id))
        with pytest.raises(EventFull):
            await use_case.execute(EventActionCommand(_user(stores), event.id))

        assert event.registered_count == 1
        assert all(call[0] != "release" for call in down.calls)  # no hubo cupo que devolver

    @pytest.mark.parametrize(
        "status", [EventStatus.DRAFT, EventStatus.FINISHED, EventStatus.CANCELLED]
    )
    async def test_only_published_events_accept_registrations(
        self, register, stores, slots, organizer, status
    ):
        event = _event(stores, organizer, status=status)
        with pytest.raises(InvalidTransition):
            await register.execute(EventActionCommand(organizer, event.id))
        assert event.id not in slots.counters  # un evento cerrado no crea contador

    async def test_foreign_draft_looks_nonexistent(self, register, stores, organizer):
        draft = _event(stores, organizer, status=EventStatus.DRAFT)
        with pytest.raises(NotFound):
            await register.execute(EventActionCommand(_user(stores), draft.id))

    async def test_expired_event_does_not_accept_registrations(
        self, register, stores, slots, organizer
    ):
        old = _event(stores, organizer, starts_in=-timedelta(days=2))  # publicado y ya terminó
        slots.counters[old.id] = 10  # aunque Redis aún crea que hay cupo
        with pytest.raises(InvalidTransition):
            await register.execute(EventActionCommand(_user(stores), old.id))
        assert slots.counters[old.id] == 10  # el cupo se devolvió

    async def test_unknown_event(self, register, stores):
        from uuid import uuid4

        with pytest.raises(NotFound):
            await register.execute(EventActionCommand(_user(stores), uuid4()))


class TestCancelEventRegistration:
    async def test_cancel_frees_the_slot_and_allows_registering_again(
        self, register, cancel, stores, slots, organizer
    ):
        event, user = _event(stores, organizer, capacity=1), _user(stores)
        await register.execute(EventActionCommand(user, event.id))

        await cancel.execute(EventActionCommand(user, event.id))

        assert event.registered_count == 0
        assert slots.counters[event.id] == 1
        await register.execute(EventActionCommand(user, event.id))  # puede volver a inscribirse
        assert event.registered_count == 1

    async def test_cancelling_also_cancels_the_users_sessions(
        self, register, cancel, stores, organizer
    ):
        event, user = _event(stores, organizer, capacity=5), _user(stores)
        speaker = make_speaker(organizer.id)
        stores.speakers[speaker.id] = speaker
        session = _session(stores, event, speaker, 1)
        await register.execute(EventActionCommand(user, event.id))
        await RegisterToSessionUseCase(
            lambda: InMemoryUnitOfWork(stores),
            FixedClock(),
            EventSync(FakeCache(), FakeSlotCounter()),
        ).execute(SessionActionCommand(user, session.id))
        assert session.registered_count == 1

        await cancel.execute(EventActionCommand(user, event.id))

        assert session.registered_count == 0
        assert all(r.cancelled_at is not None for r in stores.session_registrations.values())

    async def test_cancel_without_registration_is_not_found(self, cancel, stores, organizer):
        event = _event(stores, organizer)
        with pytest.raises(NotFound):
            await cancel.execute(EventActionCommand(_user(stores), event.id))

    async def test_cannot_cancel_after_the_event_finished(self, cancel, stores, organizer):
        event = _event(stores, organizer, status=EventStatus.FINISHED)
        with pytest.raises(InvalidTransition):
            await cancel.execute(EventActionCommand(_user(stores), event.id))


class TestSessionRegistrations:
    @pytest.fixture
    def world(self, stores, organizer):
        event = _event(stores, organizer, capacity=10)
        speaker = make_speaker(organizer.id)
        stores.speakers[speaker.id] = speaker
        return event, speaker

    @pytest.fixture
    def register_session(self, uow_factory, sync):
        return RegisterToSessionUseCase(uow_factory, FixedClock(), sync)

    async def _join(self, register, stores, event, user=None):
        user = user or _user(stores)
        await register.execute(EventActionCommand(user, event.id))
        return user

    async def test_requires_being_registered_to_the_event(self, register_session, stores, world):
        event, speaker = world
        session = _session(stores, event, speaker, 1)
        with pytest.raises(Conflict, match="inscribirte al evento"):
            await register_session.execute(SessionActionCommand(_user(stores), session.id))

    async def test_registers_and_counts(self, register_session, register, stores, world, cache):
        event, speaker = world
        session = _session(stores, event, speaker, 1)
        user = await self._join(register, stores, event)

        reg = await register_session.execute(SessionActionCommand(user, session.id))

        assert reg.session_id == session.id
        assert session.registered_count == 1

    async def test_full_session(self, register_session, register, stores, world):
        event, speaker = world
        session = _session(stores, event, speaker, 1, capacity=1)
        first = await self._join(register, stores, event)
        second = await self._join(register, stores, event)

        await register_session.execute(SessionActionCommand(first, session.id))
        with pytest.raises(SessionFull):
            await register_session.execute(SessionActionCommand(second, session.id))

        assert session.registered_count == 1

    async def test_duplicate_and_overlapping_sessions(
        self, register_session, register, stores, world
    ):
        event, speaker = world
        other_speaker = make_speaker(event.organizer_id, "Otro")
        stores.speakers[other_speaker.id] = other_speaker
        morning = _session(stores, event, speaker, 1, hours=2)  # 1h-3h
        clash = _session(stores, event, other_speaker, 2, hours=2)  # 2h-4h solapa
        after = _session(stores, event, other_speaker, 3, hours=1)  # 3h-4h no solapa
        user = await self._join(register, stores, event)

        await register_session.execute(SessionActionCommand(user, morning.id))
        with pytest.raises(AlreadyRegistered):
            await register_session.execute(SessionActionCommand(user, morning.id))
        with pytest.raises(ScheduleConflict):
            await register_session.execute(SessionActionCommand(user, clash.id))
        await register_session.execute(SessionActionCommand(user, after.id))

        assert (morning.registered_count, clash.registered_count, after.registered_count) == (
            1,
            0,
            1,
        )

    async def test_cancel_and_register_again(
        self, register_session, register, stores, world, uow_factory, sync
    ):
        event, speaker = world
        session = _session(stores, event, speaker, 1, capacity=1)
        user = await self._join(register, stores, event)
        await register_session.execute(SessionActionCommand(user, session.id))
        cancel_session = CancelSessionRegistrationUseCase(uow_factory, FixedClock(), sync)

        await cancel_session.execute(SessionActionCommand(user, session.id))
        assert session.registered_count == 0
        with pytest.raises(NotFound):
            await cancel_session.execute(SessionActionCommand(user, session.id))
        await register_session.execute(SessionActionCommand(user, session.id))
        assert session.registered_count == 1

    async def test_unknown_or_hidden_sessions(self, register_session, stores, organizer):
        from uuid import uuid4

        draft = _event(stores, organizer, status=EventStatus.DRAFT)
        hidden = _session(stores, draft, make_speaker(organizer.id), 1)
        with pytest.raises(NotFound):
            await register_session.execute(SessionActionCommand(_user(stores), uuid4()))
        with pytest.raises(NotFound):
            await register_session.execute(SessionActionCommand(_user(stores), hidden.id))


class TestListings:
    async def test_my_registrations_include_event_and_my_sessions_only(
        self, register, register_session_factory, stores, organizer
    ):
        event = _event(stores, organizer, capacity=10)
        speaker = make_speaker(organizer.id)
        stores.speakers[speaker.id] = speaker
        mine, other = _session(stores, event, speaker, 1), _session(stores, event, speaker, 3)
        me, someone = _user(stores), _user(stores)
        for u in (me, someone):
            await register.execute(EventActionCommand(u, event.id))
        await register_session_factory.execute(SessionActionCommand(me, mine.id))
        await register_session_factory.execute(SessionActionCommand(someone, other.id))

        result = await ListMyRegistrationsUseCase(lambda: InMemoryUnitOfWork(stores)).execute(
            ListMyRegistrationsQuery(me)
        )

        assert [r.event.id for r in result] == [event.id]
        assert [v.session.id for v in result[0].sessions] == [mine.id]
        assert result[0].sessions[0].speaker.id == speaker.id

    async def test_attendees_visible_only_to_owner_and_admin(
        self, register, uow_factory, stores, organizer
    ):
        event = _event(stores, organizer, capacity=10)
        users = [_user(stores) for _ in range(3)]
        for u in users:
            await register.execute(EventActionCommand(u, event.id))
        list_attendees = ListEventAttendeesUseCase(uow_factory)

        page = await list_attendees.execute(ListAttendeesQuery(organizer, event.id, page_size=2))
        assert (page.total, len(page.items)) == (3, 2)
        admin = _user(stores, Role.ADMIN)
        assert (await list_attendees.execute(ListAttendeesQuery(admin, event.id))).total == 3
        with pytest.raises(Forbidden):
            await list_attendees.execute(ListAttendeesQuery(users[0], event.id))


@pytest.fixture
def register_session_factory(uow_factory, sync):
    return RegisterToSessionUseCase(uow_factory, FixedClock(), sync)
