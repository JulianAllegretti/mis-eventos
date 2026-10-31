from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.errors import AlreadyRegistered, ScheduleConflict
from app.domain.models.event import ClosedSource, Event, EventStatus
from app.domain.models.registration import Registration, SessionRegistration
from app.domain.models.session import Session
from app.domain.models.user import Role, User
from tests.factories import make_speaker, make_user
from tests.fakes.in_memory import FIXED_NOW

NOW = datetime.now(UTC)
START = NOW + timedelta(days=10)


def _event(organizer: User, **overrides) -> Event:
    event = Event.new(
        name="Congreso",
        description=None,
        location="Bogotá",
        start_at=START,
        end_at=START + timedelta(hours=8),
        capacity=overrides.pop("capacity", 10),
        organizer_id=organizer.id,
        now=NOW,
    )
    event.status = overrides.pop("status", EventStatus.PUBLISHED)
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def _session(event: Event, speaker_id, start_h=1, hours=1, capacity=5) -> Session:
    return Session.new(
        event_id=event.id,
        speaker_id=speaker_id,
        title="Sesión",
        description=None,
        start_at=START + timedelta(hours=start_h),
        end_at=START + timedelta(hours=start_h + hours),
        capacity=capacity,
        now=NOW,
    )


@pytest.fixture
async def world(uow_factory):
    organizer, attendee = make_user(Role.ORGANIZER), make_user()
    speaker = make_speaker(organizer.id)
    event = _event(organizer)
    async with uow_factory() as uow:
        await uow.users.add(organizer)
        await uow.users.add(attendee)
        await uow.speakers.add(speaker)
        await uow.events.add(event)
        await uow.commit()
    return organizer, attendee, speaker, event


class TestSessions:
    async def test_round_trip_and_ordering(self, uow_factory, world):
        _, _, speaker, event = world
        late, early = _session(event, speaker.id, 4), _session(event, speaker.id, 1)
        async with uow_factory() as uow:
            await uow.sessions.add(late)
            await uow.sessions.add(early)
            await uow.commit()

        async with uow_factory() as uow:
            listed = await uow.sessions.list_for_event(event.id)
            assert await uow.sessions.get(early.id) == early
            assert await uow.sessions.count_for_speaker(speaker.id) == 2

        assert [s.id for s in listed] == [early.id, late.id]

    async def test_overlapping_sessions_of_one_speaker_are_rejected_by_the_database(
        self, uow_factory, world
    ):
        _, _, speaker, event = world
        async with uow_factory() as uow:
            await uow.sessions.add(_session(event, speaker.id, 1, hours=2))
            await uow.commit()

        with pytest.raises(ScheduleConflict):
            async with uow_factory() as uow:
                await uow.sessions.add(_session(event, speaker.id, 2, hours=2))
                await uow.commit()

    async def test_back_to_back_and_other_speakers_are_allowed(self, uow_factory, world):
        organizer, _, speaker, event = world
        other = make_speaker(organizer.id, "Otro")
        async with uow_factory() as uow:
            await uow.speakers.add(other)
            await uow.sessions.add(_session(event, speaker.id, 1, hours=1))
            await uow.sessions.add(_session(event, speaker.id, 2, hours=1))  # adyacente
            await uow.sessions.add(_session(event, other.id, 1, hours=2))  # otro ponente
            await uow.commit()

    async def test_speaker_overlap_query_matches_the_constraint(self, uow_factory, world):
        _, _, speaker, event = world
        existing = _session(event, speaker.id, 1, hours=2)
        async with uow_factory() as uow:
            await uow.sessions.add(existing)
            await uow.commit()

        async with uow_factory() as uow:
            probe = uow.sessions.speaker_has_overlap
            inside = (START + timedelta(hours=2), START + timedelta(hours=4))
            adjacent = (START + timedelta(hours=3), START + timedelta(hours=4))
            assert await probe(speaker.id, *inside, None) is True
            assert await probe(speaker.id, *inside, existing.id) is False  # se excluye a sí misma
            assert await probe(speaker.id, *adjacent, None) is False

    async def test_counter_increments_stop_at_capacity(self, uow_factory, world):
        _, _, speaker, event = world
        session = _session(event, speaker.id, capacity=2)
        async with uow_factory() as uow:
            await uow.sessions.add(session)
            await uow.commit()

        async with uow_factory() as uow:
            results = [await uow.sessions.try_increment_registered(session.id) for _ in range(3)]
            await uow.sessions.decrement_registered(session.id)
            await uow.commit()
            stored = await uow.sessions.get(session.id)
        assert results == [True, True, False]
        assert stored.registered_count == 1

    async def test_deleting_an_event_cascades_to_its_sessions_but_speakers_are_protected(
        self, uow_factory, world, engine
    ):
        _, _, speaker, event = world
        async with uow_factory() as uow:
            await uow.sessions.add(_session(event, speaker.id))
            await uow.commit()
        async with engine.connect() as connection:
            with pytest.raises(IntegrityError, match="foreign key"):
                await connection.execute(text("DELETE FROM speakers"))

        async with uow_factory() as uow:
            await uow.events.delete(event.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.sessions.list_for_event(event.id) == []
            assert await uow.speakers.get(speaker.id) is not None

    async def test_session_invariants_are_enforced_by_the_database(
        self, uow_factory, world, engine
    ):
        _, _, speaker, event = world
        async with uow_factory() as uow:
            await uow.sessions.add(_session(event, speaker.id, capacity=3))
            await uow.commit()
        for sql in (
            "UPDATE sessions SET capacity = 0",
            "UPDATE sessions SET end_at = start_at",
            "UPDATE sessions SET registered_count = capacity + 1",
        ):
            async with engine.connect() as connection:
                with pytest.raises(IntegrityError, match="violates check constraint"):
                    await connection.execute(text(sql))


class TestEventCounters:
    async def test_increment_respects_capacity_status_and_end_date(self, uow_factory, world):
        organizer, _, _, _ = world
        small = _event(organizer, capacity=2)
        draft = _event(organizer, status=EventStatus.DRAFT)
        over = _event(organizer, start_at=NOW - timedelta(days=3), end_at=NOW - timedelta(days=2))
        async with uow_factory() as uow:
            for e in (small, draft, over):
                await uow.events.add(e)
            await uow.commit()

        async with uow_factory() as uow:
            take = uow.events.try_increment_registered
            assert [await take(small.id, NOW) for _ in range(3)] == [True, True, False]
            assert await take(draft.id, NOW) is False
            assert await take(over.id, NOW) is False
            await uow.events.decrement_registered(small.id)
            await uow.events.decrement_registered(draft.id)  # no baja de cero
            await uow.commit()
            assert (await uow.events.get(small.id)).registered_count == 1
            assert (await uow.events.get(draft.id)).registered_count == 0

    async def test_finish_expired_closes_as_scheduler_and_is_idempotent(
        self, uow_factory, world, engine
    ):
        organizer, _, _, _ = world
        expired = _event(
            organizer, start_at=NOW - timedelta(days=3), end_at=NOW - timedelta(days=2)
        )
        running = _event(
            organizer, start_at=NOW - timedelta(hours=1), end_at=NOW + timedelta(hours=3)
        )
        async with uow_factory() as uow:
            await uow.events.add(expired)
            await uow.events.add(running)
            await uow.commit()

        async with uow_factory() as uow:
            closed = await uow.events.finish_expired(NOW)
            await uow.commit()
        async with uow_factory() as uow:
            again = await uow.events.finish_expired(NOW)
            stored = await uow.events.get(expired.id)
            still_running = await uow.events.get(running.id)

        assert closed == [expired.id]
        assert again == []
        assert stored.status is EventStatus.FINISHED
        assert (stored.closed_by_id, stored.closed_source) == (None, ClosedSource.SCHEDULER)
        assert stored.closed_at is not None
        assert still_running.status is EventStatus.PUBLISHED

    async def test_availability_listing_only_includes_open_published_events(
        self, uow_factory, world
    ):
        organizer, _, _, event = world
        async with uow_factory() as uow:
            await uow.events.add(_event(organizer, status=EventStatus.DRAFT))
            await uow.events.add(
                _event(organizer, start_at=NOW - timedelta(days=3), end_at=NOW - timedelta(days=2))
            )
            await uow.events.try_increment_registered(event.id, NOW)
            await uow.commit()

        async with uow_factory() as uow:
            availability = await uow.events.list_open_availability(NOW)

        assert availability == [(event.id, 9)]


class TestRegistrations:
    async def test_one_active_registration_per_user_and_event(self, uow_factory, world):
        _, attendee, _, event = world
        async with uow_factory() as uow:
            await uow.registrations.add(
                Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
            )
            await uow.commit()

        with pytest.raises(AlreadyRegistered):
            async with uow_factory() as uow:
                await uow.registrations.add(
                    Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
                )

    async def test_can_register_again_after_cancelling(self, uow_factory, world):
        _, attendee, _, event = world
        async with uow_factory() as uow:
            await uow.registrations.add(
                Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
            )
            assert await uow.registrations.cancel(attendee.id, event.id, NOW) is True
            assert await uow.registrations.cancel(attendee.id, event.id, NOW) is False
            await uow.registrations.add(
                Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
            )
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.registrations.get_active(attendee.id, event.id) is not None
            assert await uow.registrations.exists_for_event(event.id) is True

    async def test_listings(self, uow_factory, world):
        _, attendee, _, event = world
        async with uow_factory() as uow:
            await uow.registrations.add(
                Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
            )
            await uow.commit()

        async with uow_factory() as uow:
            mine = await uow.registrations.list_active_for_user(attendee.id)
            attendees, total = await uow.registrations.list_attendees(event.id, 10, 0)

        assert [e.id for _, e in mine] == [event.id]
        assert (total, [u.id for _, u in attendees]) == (1, [attendee.id])

    async def test_users_and_events_with_registrations_cannot_be_deleted(
        self, uow_factory, world, engine
    ):
        _, attendee, _, event = world
        async with uow_factory() as uow:
            await uow.registrations.add(
                Registration.new(user_id=attendee.id, event_id=event.id, now=NOW)
            )
            await uow.commit()
        async with engine.connect() as connection:
            with pytest.raises(IntegrityError, match="foreign key"):
                await connection.execute(text("DELETE FROM events"))


class TestSessionRegistrations:
    async def _setup(self, uow_factory, world):
        _, attendee, speaker, event = world
        first, second = _session(event, speaker.id, 1, hours=2), _session(event, speaker.id, 4)
        async with uow_factory() as uow:
            await uow.sessions.add(first)
            await uow.sessions.add(second)
            await uow.commit()
        return attendee, event, first, second

    async def test_unique_active_registration_and_overlap_detection(self, uow_factory, world):
        attendee, _, first, second = await self._setup(uow_factory, world)
        async with uow_factory() as uow:
            await uow.session_registrations.add(
                SessionRegistration.new(user_id=attendee.id, session_id=first.id, now=NOW)
            )
            await uow.commit()

        async with uow_factory() as uow:
            repo = uow.session_registrations
            assert (
                await repo.has_overlap(
                    attendee.id, first.start_at + timedelta(minutes=30), first.end_at
                )
                is True
            )
            assert await repo.has_overlap(attendee.id, second.start_at, second.end_at) is False
            assert (await repo.get_active(attendee.id, first.id)) is not None
            with pytest.raises(AlreadyRegistered):
                await repo.add(
                    SessionRegistration.new(user_id=attendee.id, session_id=first.id, now=NOW)
                )

    async def test_cancelled_registrations_do_not_count_for_overlap(self, uow_factory, world):
        attendee, _, first, _ = await self._setup(uow_factory, world)
        async with uow_factory() as uow:
            repo = uow.session_registrations
            await repo.add(
                SessionRegistration.new(user_id=attendee.id, session_id=first.id, now=NOW)
            )
            assert await repo.cancel(attendee.id, first.id, NOW) is True
            assert await repo.has_overlap(attendee.id, first.start_at, first.end_at) is False
            await uow.commit()

    async def test_cancel_all_for_event_returns_the_sessions_and_listing_is_ordered(
        self, uow_factory, world
    ):
        attendee, event, first, second = await self._setup(uow_factory, world)
        async with uow_factory() as uow:
            repo = uow.session_registrations
            await repo.add(
                SessionRegistration.new(user_id=attendee.id, session_id=second.id, now=NOW)
            )
            await repo.add(
                SessionRegistration.new(user_id=attendee.id, session_id=first.id, now=NOW)
            )
            await uow.commit()
        async with uow_factory() as uow:
            listed = await uow.session_registrations.list_active_for_user(attendee.id)
            cancelled = await uow.session_registrations.cancel_all_for_event(
                attendee.id, event.id, NOW
            )
            await uow.commit()
        async with uow_factory() as uow:
            remaining = await uow.session_registrations.list_active_for_user(attendee.id)

        assert [s.id for _, s in listed] == [first.id, second.id]
        assert sorted(cancelled, key=str) == sorted([first.id, second.id], key=str)
        assert remaining == []

    async def test_deleting_a_session_removes_its_registrations(self, uow_factory, world, engine):
        attendee, _, first, _ = await self._setup(uow_factory, world)
        async with uow_factory() as uow:
            await uow.session_registrations.add(
                SessionRegistration.new(user_id=attendee.id, session_id=first.id, now=NOW)
            )
            await uow.commit()
        async with uow_factory() as uow:
            await uow.sessions.delete(first.id)
            await uow.commit()
        async with engine.connect() as connection:
            count = (
                await connection.execute(text("SELECT count(*) FROM session_registrations"))
            ).scalar_one()
        assert count == 0


def test_fixed_now_is_not_used_by_database_tests():
    # Estas pruebas usan la hora real para que el filtro `end_at >= now` de PostgreSQL sea realista.
    assert FIXED_NOW != NOW
