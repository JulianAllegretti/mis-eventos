from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.dto.commands import (
    CreateSessionCommand,
    SessionActionCommand,
    SpeakerActionCommand,
    UpdateEventCommand,
    UpdateSessionCommand,
)
from app.application.dto.queries import ListEventSessionsQuery
from app.application.services.event_sync import EventSync
from app.application.use_cases.events.update_event import UpdateEventUseCase
from app.application.use_cases.sessions.manage_sessions import (
    CreateSessionUseCase,
    DeleteSessionUseCase,
    ListEventSessionsUseCase,
    UpdateSessionUseCase,
)
from app.application.use_cases.speakers.manage_speakers import DeleteSpeakerUseCase
from app.domain.errors import (
    Conflict,
    Forbidden,
    InvalidTransition,
    NotFound,
    ScheduleConflict,
    ValidationFailed,
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

EVENT_START = FIXED_NOW + timedelta(days=10)  # make_event: 8 horas desde aquí


@pytest.fixture
def stores():
    return make_stores()


@pytest.fixture
def uow_factory(stores):
    return lambda: InMemoryUnitOfWork(stores)


@pytest.fixture
def cache():
    return FakeCache()


@pytest.fixture
def sync(cache):
    return EventSync(cache, FakeSlotCounter())


@pytest.fixture
def owner(stores):
    user = make_user(Role.ORGANIZER)
    stores.users[user.id] = user
    return user


@pytest.fixture
def event(stores, owner):
    event = make_event(owner.id, status=EventStatus.PUBLISHED, capacity=100)
    stores.events[event.id] = event
    return event


@pytest.fixture
def speaker(stores, owner):
    speaker = make_speaker(owner.id)
    stores.speakers[speaker.id] = speaker
    return speaker


def _cmd(actor, event, speaker, **overrides):
    base = {
        "title": "Introducción a FastAPI",
        "description": None,
        "start_at": EVENT_START + timedelta(hours=1),
        "end_at": EVENT_START + timedelta(hours=2),
        "capacity": 30,
    }
    return CreateSessionCommand(
        actor=actor, event_id=event.id, speaker_id=speaker.id, **{**base, **overrides}
    )


def _add_session(stores, event, speaker, start_hour=1, hours=1, capacity=30, registered=0):
    session = Session.new(
        event_id=event.id,
        speaker_id=speaker.id,
        title="Existente",
        description=None,
        start_at=EVENT_START + timedelta(hours=start_hour),
        end_at=EVENT_START + timedelta(hours=start_hour + hours),
        capacity=capacity,
        now=FIXED_NOW,
    )
    session.registered_count = registered
    stores.sessions[session.id] = session
    return session


class TestCreateSession:
    async def test_owner_creates_a_session_with_speaker(
        self, uow_factory, sync, owner, event, speaker, cache
    ):
        view = await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
            _cmd(owner, event, speaker)
        )

        assert view.session.event_id == event.id
        assert view.speaker.name == speaker.name
        assert view.session.registered_count == 0
        assert cache.versions["events"] == 1  # la caché de lectura se invalidó

    async def test_other_organizer_and_attendee_are_forbidden(
        self, uow_factory, sync, event, speaker
    ):
        use_case = CreateSessionUseCase(uow_factory, FixedClock(), sync)
        for role in (Role.ORGANIZER, Role.ATTENDEE):
            with pytest.raises(Forbidden):
                await use_case.execute(_cmd(make_user(role), event, speaker))

    @pytest.mark.parametrize(
        "overrides",
        [
            {"start_at": EVENT_START - timedelta(hours=1)},  # antes del evento
            {"end_at": EVENT_START + timedelta(hours=9)},  # después del evento
            {"end_at": EVENT_START + timedelta(hours=1)},  # fin == inicio
            {"capacity": 101},  # más que el evento
            {"capacity": 0},
            {"title": "  "},
        ],
    )
    async def test_invalid_data_is_rejected(
        self, uow_factory, sync, owner, event, speaker, overrides
    ):
        with pytest.raises(ValidationFailed):
            await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
                _cmd(owner, event, speaker, **overrides)
            )

    async def test_unknown_speaker_is_not_found(self, uow_factory, sync, owner, event):
        with pytest.raises(NotFound):
            await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
                _cmd(owner, event, make_speaker(owner.id))
            )

    async def test_speaker_cannot_be_in_two_overlapping_sessions(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        _add_session(stores, event, speaker, start_hour=1, hours=2)  # 1h-3h
        use_case = CreateSessionUseCase(uow_factory, FixedClock(), sync)

        with pytest.raises(ScheduleConflict):
            await use_case.execute(
                _cmd(
                    owner,
                    event,
                    speaker,
                    start_at=EVENT_START + timedelta(hours=2),
                    end_at=EVENT_START + timedelta(hours=4),
                )
            )

    async def test_back_to_back_sessions_do_not_overlap(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        _add_session(stores, event, speaker, start_hour=1, hours=1)  # termina a las 2h
        await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
            _cmd(
                owner,
                event,
                speaker,
                start_at=EVENT_START + timedelta(hours=2),
                end_at=EVENT_START + timedelta(hours=3),
            )
        )
        assert len(stores.sessions) == 2

    async def test_different_speakers_can_run_in_parallel(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        _add_session(stores, event, speaker)
        other = make_speaker(owner.id, "Luis")
        stores.speakers[other.id] = other

        await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
            _cmd(owner, event, other)  # mismo horario, otro ponente
        )

        assert len(stores.sessions) == 2

    @pytest.mark.parametrize("status", [EventStatus.FINISHED, EventStatus.CANCELLED])
    async def test_closed_events_do_not_accept_sessions(
        self, uow_factory, sync, owner, event, speaker, status
    ):
        event.status = status
        with pytest.raises(InvalidTransition):
            await CreateSessionUseCase(uow_factory, FixedClock(), sync).execute(
                _cmd(owner, event, speaker)
            )


class TestUpdateAndDeleteSession:
    async def test_partial_update(self, uow_factory, sync, stores, owner, event, speaker):
        session = _add_session(stores, event, speaker)

        view = await UpdateSessionUseCase(uow_factory, FixedClock(), sync).execute(
            UpdateSessionCommand(owner, session.id, {"title": "Nuevo título", "capacity": 40})
        )

        assert (view.session.title, view.session.capacity) == ("Nuevo título", 40)

    async def test_session_may_move_without_clashing_with_itself(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        session = _add_session(stores, event, speaker, start_hour=1, hours=2)
        view = await UpdateSessionUseCase(uow_factory, FixedClock(), sync).execute(
            UpdateSessionCommand(
                owner,
                session.id,
                {
                    "start_at": EVENT_START + timedelta(hours=2),
                    "end_at": EVENT_START + timedelta(hours=4),
                },
            )
        )
        assert view.session.start_at == EVENT_START + timedelta(hours=2)

    async def test_registered_sessions_keep_their_schedule(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        session = _add_session(stores, event, speaker, registered=3)
        use_case = UpdateSessionUseCase(uow_factory, FixedClock(), sync)

        with pytest.raises(Conflict):
            await use_case.execute(
                UpdateSessionCommand(
                    owner,
                    session.id,
                    {
                        "start_at": EVENT_START + timedelta(hours=2),
                        "end_at": EVENT_START + timedelta(hours=3),
                    },
                )
            )
        with pytest.raises(ValidationFailed):  # capacidad por debajo de los inscritos
            await use_case.execute(UpdateSessionCommand(owner, session.id, {"capacity": 2}))
        ok = await use_case.execute(UpdateSessionCommand(owner, session.id, {"capacity": 3}))
        assert ok.session.capacity == 3

    async def test_rejects_unknown_and_null_fields(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        session = _add_session(stores, event, speaker)
        use_case = UpdateSessionUseCase(uow_factory, FixedClock(), sync)
        with pytest.raises(ValidationFailed):
            await use_case.execute(UpdateSessionCommand(owner, session.id, {"event_id": "x"}))
        with pytest.raises(ValidationFailed):
            await use_case.execute(UpdateSessionCommand(owner, session.id, {"title": None}))

    async def test_delete_only_without_registrations(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        busy = _add_session(stores, event, speaker, start_hour=1, registered=1)
        free = _add_session(stores, event, speaker, start_hour=3)
        use_case = DeleteSessionUseCase(uow_factory, FixedClock(), sync)

        with pytest.raises(Conflict):
            await use_case.execute(SessionActionCommand(owner, busy.id))
        await use_case.execute(SessionActionCommand(owner, free.id))
        assert list(stores.sessions) == [busy.id]

    async def test_other_organizer_cannot_touch_sessions(
        self, uow_factory, sync, stores, event, speaker
    ):
        session = _add_session(stores, event, speaker)
        intruder = make_user(Role.ORGANIZER)
        with pytest.raises(Forbidden):
            await DeleteSessionUseCase(uow_factory, FixedClock(), sync).execute(
                SessionActionCommand(intruder, session.id)
            )


class TestListAndEventConsistency:
    async def test_lists_sessions_ordered_with_their_speaker(
        self, uow_factory, stores, event, speaker
    ):
        later = _add_session(stores, event, speaker, start_hour=4)
        earlier = _add_session(stores, event, speaker, start_hour=1)

        views = await ListEventSessionsUseCase(uow_factory).execute(
            ListEventSessionsQuery(viewer=None, event_id=event.id)
        )

        assert [v.session.id for v in views] == [earlier.id, later.id]
        assert views[0].speaker.name == speaker.name

    async def test_draft_event_sessions_are_hidden_from_the_public(
        self, uow_factory, stores, owner
    ):
        draft = make_event(owner.id)
        stores.events[draft.id] = draft
        with pytest.raises(NotFound):
            await ListEventSessionsUseCase(uow_factory).execute(
                ListEventSessionsQuery(viewer=None, event_id=draft.id)
            )

    async def test_event_cannot_shrink_below_its_sessions(
        self, uow_factory, sync, stores, owner, event, speaker
    ):
        _add_session(stores, event, speaker, start_hour=6, hours=2, capacity=50)  # 6h-8h
        update = UpdateEventUseCase(uow_factory, FixedClock(), sync)

        with pytest.raises(ValidationFailed):  # el nuevo fin deja la sesión fuera
            await update.execute(
                UpdateEventCommand(owner, event.id, {"end_at": EVENT_START + timedelta(hours=6)})
            )
        with pytest.raises(ValidationFailed):  # la capacidad quedaría por debajo de la sesión
            await update.execute(UpdateEventCommand(owner, event.id, {"capacity": 40}))
        ok = await update.execute(UpdateEventCommand(owner, event.id, {"capacity": 50}))
        assert ok.capacity == 50

    async def test_speaker_with_sessions_cannot_be_deleted(
        self, uow_factory, stores, owner, event, speaker
    ):
        session = _add_session(stores, event, speaker)
        use_case = DeleteSpeakerUseCase(uow_factory)

        with pytest.raises(Conflict):
            await use_case.execute(SpeakerActionCommand(owner, speaker.id))
        del stores.sessions[session.id]
        await use_case.execute(SpeakerActionCommand(owner, speaker.id))
        assert speaker.id not in stores.speakers

    async def test_random_ids_are_not_found(self, uow_factory, sync, owner):
        with pytest.raises(NotFound):
            await DeleteSessionUseCase(uow_factory, FixedClock(), sync).execute(
                SessionActionCommand(owner, uuid4())
            )
