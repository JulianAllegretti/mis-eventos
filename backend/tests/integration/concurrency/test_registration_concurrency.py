"""Carreras reales contra PostgreSQL y Redis (ADR 0005).

Cada prueba lanza decenas de tareas simultáneas y comprueba que nunca hay sobreventa, que los
duplicados se rechazan y que los contadores quedan coherentes con la base de datos.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.adapters.outbound.cache.null_adapters import NullCache, NullSlotCounter
from app.adapters.outbound.cache.redis_client import create_redis
from app.adapters.outbound.cache.redis_slot_counter import RedisSlotCounter
from app.adapters.outbound.system.system_clock import SystemClock
from app.application.dto.commands import (
    CreateSessionCommand,
    EventActionCommand,
    SessionActionCommand,
)
from app.application.services.event_sync import EventSync
from app.application.use_cases.events.maintenance import (
    FinishExpiredEventsUseCase,
    ReconcileSlotsUseCase,
)
from app.application.use_cases.registrations.event_registrations import (
    CancelEventRegistrationUseCase,
    RegisterToEventUseCase,
)
from app.application.use_cases.registrations.session_registrations import (
    RegisterToSessionUseCase,
)
from app.application.use_cases.sessions.manage_sessions import CreateSessionUseCase
from app.domain.errors import (
    AlreadyRegistered,
    EventFull,
    ScheduleConflict,
    SessionFull,
)
from app.domain.models.event import Event, EventStatus
from app.domain.models.registration import Registration
from app.domain.models.session import Session
from app.domain.models.user import Role, User
from tests.factories import make_speaker, make_user
from tests.fakes.in_memory import FakeMetrics

START = datetime.now(UTC) + timedelta(days=10)


@pytest.fixture(params=["redis", "sin-redis"])
def slots(request):
    """Cada escenario se ejecuta con el filtro de Redis y también solo con PostgreSQL."""
    if request.param == "redis":
        return RedisSlotCounter(request.getfixturevalue("redis_client"))
    return NullSlotCounter()


@pytest.fixture
def clock():
    return SystemClock()


@pytest.fixture
def sync(slots):
    return EventSync(NullCache(), slots)


@pytest.fixture
def register(uow_factory, clock, slots, sync):
    return RegisterToEventUseCase(uow_factory, clock, slots, sync, FakeMetrics())


async def _create_event(uow_factory, capacity) -> tuple[User, Event]:
    organizer = make_user(Role.ORGANIZER)
    event = Event.new(
        name="Congreso",
        description=None,
        location="Bogotá",
        start_at=START,
        end_at=START + timedelta(hours=8),
        capacity=capacity,
        organizer_id=organizer.id,
        now=datetime.now(UTC),
    )
    event.status = EventStatus.PUBLISHED
    async with uow_factory() as uow:
        await uow.users.add(organizer)
        await uow.events.add(event)
        await uow.commit()
    return organizer, event


async def _create_users(uow_factory, count) -> list[User]:
    users = [make_user() for _ in range(count)]
    async with uow_factory() as uow:
        for user in users:
            await uow.users.add(user)
        await uow.commit()
    return users


async def _state(engine, event_id):
    """(registered_count, inscripciones activas) tal como las ve PostgreSQL."""
    async with engine.connect() as connection:
        counted = (
            await connection.execute(
                text("SELECT registered_count FROM events WHERE id = :id"), {"id": event_id}
            )
        ).scalar_one()
        active = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM registrations "
                    "WHERE event_id = :id AND cancelled_at IS NULL"
                ),
                {"id": event_id},
            )
        ).scalar_one()
    return counted, active


def _outcomes(results):
    ok = [r for r in results if isinstance(r, Registration)]
    errors = [r for r in results if isinstance(r, Exception)]
    unexpected = [e for e in errors if not isinstance(e, (EventFull, AlreadyRegistered))]
    assert not unexpected, f"errores inesperados: {unexpected!r}"
    return ok, errors


class TestEventCapacityRace:
    @pytest.mark.parametrize(("capacity", "users"), [(1, 30), (5, 40)])
    async def test_never_sells_more_than_the_capacity(
        self, uow_factory, engine, register, capacity, users
    ):
        _, event = await _create_event(uow_factory, capacity)
        attendees = await _create_users(uow_factory, users)

        results = await asyncio.gather(
            *(register.execute(EventActionCommand(u, event.id)) for u in attendees),
            return_exceptions=True,
        )

        ok, errors = _outcomes(results)
        assert len(ok) == capacity
        assert len(errors) == users - capacity
        assert all(isinstance(e, EventFull) for e in errors)
        assert await _state(engine, event.id) == (capacity, capacity)

    async def test_the_redis_counter_ends_at_zero_when_the_event_sells_out(
        self, uow_factory, register, redis_client
    ):
        _, event = await _create_event(uow_factory, 3)
        attendees = await _create_users(uow_factory, 20)
        # este escenario inspecciona Redis, así que solo aplica con el filtro activo
        if not isinstance(register._slots, RedisSlotCounter):
            pytest.skip("escenario específico de Redis")

        await asyncio.gather(
            *(register.execute(EventActionCommand(u, event.id)) for u in attendees),
            return_exceptions=True,
        )

        assert int(await redis_client.get(f"slots:event:{event.id}")) == 0

    async def test_a_double_click_registers_only_once(self, uow_factory, engine, register, slots):
        _, event = await _create_event(uow_factory, 10)
        (user,) = await _create_users(uow_factory, 1)

        results = await asyncio.gather(
            *(register.execute(EventActionCommand(user, event.id)) for _ in range(15)),
            return_exceptions=True,
        )

        ok, errors = _outcomes(results)
        assert len(ok) == 1
        assert all(isinstance(e, AlreadyRegistered) for e in errors)  # el candado los colapsa
        assert await _state(engine, event.id) == (1, 1)
        if isinstance(slots, RedisSlotCounter):
            # Los duplicados ni siquiera tocaron el contador: solo se descontó la inscripción real.
            assert int(await slots._client.get(f"slots:event:{event.id}")) == 9

    async def test_duplicate_attempts_return_their_slot(
        self, uow_factory, engine, register, slots, redis_client
    ):
        """Con clics dobles, las fallidas devuelven el cupo: otro usuario aún puede entrar."""
        _, event = await _create_event(uow_factory, 2)
        first, second = await _create_users(uow_factory, 2)

        await asyncio.gather(
            *(register.execute(EventActionCommand(first, event.id)) for _ in range(10)),
            return_exceptions=True,
        )
        await register.execute(EventActionCommand(second, event.id))  # no debe lanzar EventFull

        assert await _state(engine, event.id) == (2, 2)

    async def test_many_users_each_double_clicking(self, uow_factory, engine, register):
        _, event = await _create_event(uow_factory, 4)
        attendees = await _create_users(uow_factory, 25)

        results = await asyncio.gather(
            *(
                register.execute(EventActionCommand(u, event.id))
                for u in attendees
                for _ in range(2)
            ),
            return_exceptions=True,
        )

        ok, _ = _outcomes(results)
        assert len(ok) == 4
        assert len({r.user_id for r in ok}) == 4
        assert await _state(engine, event.id) == (4, 4)

    async def test_register_cancel_churn_keeps_the_counters_consistent(
        self, uow_factory, engine, clock, slots, sync
    ):
        _, event = await _create_event(uow_factory, 3)
        attendees = await _create_users(uow_factory, 20)
        register = RegisterToEventUseCase(uow_factory, clock, slots, sync, FakeMetrics())
        cancel = CancelEventRegistrationUseCase(uow_factory, clock, slots, sync)

        async def wave():
            return await asyncio.gather(
                *(register.execute(EventActionCommand(u, event.id)) for u in attendees),
                return_exceptions=True,
            )

        first = await wave()
        winners = [u for u, r in zip(attendees, first, strict=True) if isinstance(r, Registration)]
        assert len(winners) == 3
        await asyncio.gather(*(cancel.execute(EventActionCommand(u, event.id)) for u in winners))
        assert await _state(engine, event.id) == (0, 0)

        second = await wave()  # los 20 vuelven a competir por los 3 cupos liberados

        assert sum(isinstance(r, Registration) for r in second) == 3
        counted, active = await _state(engine, event.id)
        assert counted == active == 3


class TestRedisFailureModes:
    async def test_a_drifted_counter_cannot_cause_overselling(
        self, uow_factory, engine, register, redis_client
    ):
        if not isinstance(register._slots, RedisSlotCounter):
            pytest.skip("escenario específico de Redis")
        _, event = await _create_event(uow_factory, 3)
        attendees = await _create_users(uow_factory, 30)
        await redis_client.set(f"slots:event:{event.id}", 1000)  # el contador cree que hay mucho

        results = await asyncio.gather(
            *(register.execute(EventActionCommand(u, event.id)) for u in attendees),
            return_exceptions=True,
        )

        ok, _ = _outcomes(results)
        assert len(ok) == 3  # PostgreSQL manda
        assert await _state(engine, event.id) == (3, 3)
        assert int(await redis_client.get(f"slots:event:{event.id}")) == 997  # solo cuentan las 3

    async def test_reconciliation_repairs_a_corrupted_counter(
        self, uow_factory, clock, register, slots, redis_client
    ):
        if not isinstance(slots, RedisSlotCounter):
            pytest.skip("escenario específico de Redis")
        _, event = await _create_event(uow_factory, 5)
        (user,) = await _create_users(uow_factory, 1)
        await register.execute(EventActionCommand(user, event.id))
        await redis_client.set(f"slots:event:{event.id}", 0)  # desvío: dice lleno

        await ReconcileSlotsUseCase(uow_factory, clock, slots).execute()

        assert int(await redis_client.get(f"slots:event:{event.id}")) == 4

    async def test_a_dead_redis_does_not_stop_registrations(self, uow_factory, engine, clock):
        dead = RedisSlotCounter(create_redis("redis://127.0.0.1:1/0"))
        register = RegisterToEventUseCase(
            uow_factory, clock, dead, EventSync(NullCache(), dead), FakeMetrics()
        )
        _, event = await _create_event(uow_factory, 3)
        attendees = await _create_users(uow_factory, 20)

        results = await asyncio.gather(
            *(register.execute(EventActionCommand(u, event.id)) for u in attendees),
            return_exceptions=True,
        )

        ok, _ = _outcomes(results)
        assert len(ok) == 3
        assert await _state(engine, event.id) == (3, 3)


class TestSessionRaces:
    async def _agenda(self, uow_factory, sessions_spec):
        """sessions_spec: lista de (hora_inicio, horas, capacidad). Devuelve evento y sesiones."""
        organizer, event = await _create_event(uow_factory, 100)
        speakers = [make_speaker(organizer.id, f"Ponente {i}") for i in range(len(sessions_spec))]
        sessions = [
            Session.new(
                event_id=event.id,
                speaker_id=speaker.id,
                title=f"S{i}",
                description=None,
                start_at=START + timedelta(hours=start),
                end_at=START + timedelta(hours=start + hours),
                capacity=capacity,
                now=datetime.now(UTC),
            )
            for i, (speaker, (start, hours, capacity)) in enumerate(
                zip(speakers, sessions_spec, strict=True)
            )
        ]
        async with uow_factory() as uow:
            for speaker in speakers:
                await uow.speakers.add(speaker)
            for session in sessions:
                await uow.sessions.add(session)
            await uow.commit()
        return organizer, event, sessions

    async def _join_event(self, register, users, event):
        for user in users:
            await register.execute(EventActionCommand(user, event.id))

    async def test_a_full_session_never_exceeds_its_capacity(
        self, uow_factory, clock, register, sync
    ):
        _, event, (session,) = await self._agenda(uow_factory, [(1, 1, 2)])
        attendees = await _create_users(uow_factory, 12)
        await self._join_event(register, attendees, event)
        enroll = RegisterToSessionUseCase(uow_factory, clock, sync)

        results = await asyncio.gather(
            *(enroll.execute(SessionActionCommand(u, session.id)) for u in attendees),
            return_exceptions=True,
        )

        assert sum(not isinstance(r, Exception) for r in results) == 2
        assert all(isinstance(r, SessionFull) for r in results if isinstance(r, Exception))
        async with uow_factory() as uow:
            assert (await uow.sessions.get(session.id)).registered_count == 2

    async def test_one_user_cannot_join_two_overlapping_sessions_at_once(
        self, uow_factory, clock, register, sync
    ):
        _, event, (first, second) = await self._agenda(uow_factory, [(1, 2, 10), (2, 2, 10)])
        (user,) = await _create_users(uow_factory, 1)
        await self._join_event(register, [user], event)
        enroll = RegisterToSessionUseCase(uow_factory, clock, sync)

        results = await asyncio.gather(
            enroll.execute(SessionActionCommand(user, first.id)),
            enroll.execute(SessionActionCommand(user, second.id)),
            return_exceptions=True,
        )

        assert sum(not isinstance(r, Exception) for r in results) == 1
        assert sum(isinstance(r, ScheduleConflict) for r in results) == 1

    async def test_two_overlapping_sessions_for_one_speaker_cannot_both_be_created(
        self, uow_factory, clock, sync
    ):
        organizer, event, _ = await self._agenda(uow_factory, [(7, 1, 5)])
        speaker = make_speaker(organizer.id, "Ponente compartido")
        async with uow_factory() as uow:
            await uow.speakers.add(speaker)
            await uow.commit()
        create = CreateSessionUseCase(uow_factory, clock, sync)

        def command(start, hours):
            return CreateSessionCommand(
                actor=organizer,
                event_id=event.id,
                speaker_id=speaker.id,
                title="Charla",
                description=None,
                start_at=START + timedelta(hours=start),
                end_at=START + timedelta(hours=start + hours),
                capacity=5,
            )

        # Ambas pasan la comprobación previa a la vez: solo la restricción EXCLUDE las distingue.
        results = await asyncio.gather(
            *(create.execute(command(1, 2)) for _ in range(2)),
            create.execute(command(2, 2)),
            return_exceptions=True,
        )

        created = [r for r in results if not isinstance(r, Exception)]
        assert len(created) == 1
        assert all(isinstance(r, ScheduleConflict) for r in results if isinstance(r, Exception))
        async with uow_factory() as uow:
            assert await uow.sessions.count_for_speaker(speaker.id) == 1


class TestSchedulerRace:
    async def test_two_workers_close_each_expired_event_exactly_once(
        self, uow_factory, clock, slots, sync, engine
    ):
        organizer = make_user(Role.ORGANIZER)
        now = datetime.now(UTC)
        expired = [
            Event.new(
                name=f"Vencido {i}",
                description=None,
                location="Bogotá",
                start_at=now - timedelta(days=3),
                end_at=now - timedelta(days=2),
                capacity=5,
                organizer_id=organizer.id,
                now=now - timedelta(days=4),
            )
            for i in range(5)
        ]
        for event in expired:
            event.status = EventStatus.PUBLISHED
        async with uow_factory() as uow:
            await uow.users.add(organizer)
            for event in expired:
                await uow.events.add(event)
            await uow.commit()
        job = FinishExpiredEventsUseCase(uow_factory, clock, slots, sync, FakeMetrics())

        batches = await asyncio.gather(*(job.execute() for _ in range(4)))

        closed = [event_id for batch in batches for event_id in batch]
        assert sorted(closed, key=str) == sorted((e.id for e in expired), key=str)  # sin repetidos
        async with engine.connect() as connection:
            sources = (
                (await connection.execute(text("SELECT DISTINCT closed_source FROM events")))
                .scalars()
                .all()
            )
        assert sources == ["scheduler"]
