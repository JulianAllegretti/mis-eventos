from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.dto.queries import EventSearchCriteria
from app.domain.models.event import ClosedSource, EventStatus
from app.domain.models.user import Role
from tests.factories import make_event, make_speaker, make_user
from tests.fakes.in_memory import FIXED_NOW


def _criteria(**overrides) -> EventSearchCriteria:
    base = {
        "now": FIXED_NOW,
        "q": None,
        "status": None,
        "organizer_id": None,
        "exclude_drafts": False,
        "limit": 50,
        "offset": 0,
    }
    return EventSearchCriteria(**{**base, **overrides})


@pytest.fixture
async def organizer(uow_factory):
    user = make_user(Role.ORGANIZER)
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()
    return user


async def _save(uow_factory, *events):
    async with uow_factory() as uow:
        for event in events:
            await uow.events.add(event)
        await uow.commit()


async def _search(uow_factory, **overrides):
    async with uow_factory() as uow:
        return await uow.events.search(_criteria(**overrides))


async def test_event_round_trip_with_timezone_and_closing_fields(uow_factory, organizer):
    event = make_event(organizer.id, status=EventStatus.PUBLISHED, capacity=40, registered=5)
    await _save(uow_factory, event)

    async with uow_factory() as uow:
        stored = await uow.events.get(event.id)
        assert stored == event
        assert stored.start_at.tzinfo is not None

        stored.status = EventStatus.FINISHED
        stored.closed_at = FIXED_NOW
        stored.closed_by_id = organizer.id
        stored.closed_source = ClosedSource.MANUAL
        await uow.events.update(stored)
        await uow.commit()

    async with uow_factory() as uow:
        reloaded = await uow.events.get(event.id)
    assert reloaded.status is EventStatus.FINISHED
    assert (reloaded.closed_by_id, reloaded.closed_source) == (organizer.id, ClosedSource.MANUAL)


async def test_search_matches_part_of_name_ignoring_case_and_accents_free(uow_factory, organizer):
    await _save(
        uow_factory,
        make_event(organizer.id, name="Congreso de Python"),
        make_event(organizer.id, name="Taller PYTHON avanzado"),
        make_event(organizer.id, name="Charla de Rust"),
    )

    events, total = await _search(uow_factory, q="pyth")

    assert total == 2
    assert {e.name for e in events} == {"Congreso de Python", "Taller PYTHON avanzado"}


async def test_like_wildcards_in_user_text_are_literal(uow_factory, organizer):
    await _save(
        uow_factory,
        make_event(organizer.id, name="100% Python"),
        make_event(organizer.id, name="Python"),
        make_event(organizer.id, name="snake_case day"),
        make_event(organizer.id, name="snakeXcase day"),
    )

    assert [e.name for e in (await _search(uow_factory, q="%"))[0]] == ["100% Python"]
    assert [e.name for e in (await _search(uow_factory, q="_"))[0]] == ["snake_case day"]
    assert (await _search(uow_factory, q="\\"))[1] == 0


@pytest.mark.parametrize(
    "payload", ["' OR '1'='1", "'; DROP TABLE events; --", '" OR ""="', "%' OR 1=1 --"]
)
async def test_sql_injection_attempts_are_inert(uow_factory, organizer, engine, payload):
    await _save(uow_factory, make_event(organizer.id, name="Evento normal"))

    events, total = await _search(uow_factory, q=payload)

    assert (events, total) == ([], 0)
    async with engine.connect() as connection:
        count = (await connection.execute(text("SELECT count(*) FROM events"))).scalar_one()
    assert count == 1  # la tabla sigue existiendo y con sus datos


async def test_effective_status_filter_in_sql(uow_factory, organizer):
    await _save(
        uow_factory,
        make_event(
            organizer.id, name="Vencido", status=EventStatus.PUBLISHED, starts_in=-timedelta(days=2)
        ),
        make_event(organizer.id, name="Vigente", status=EventStatus.PUBLISHED),
    )

    finished, _ = await _search(uow_factory, status=EventStatus.FINISHED)
    published, _ = await _search(uow_factory, status=EventStatus.PUBLISHED)

    assert [e.name for e in finished] == ["Vencido"]
    assert [e.name for e in published] == ["Vigente"]


async def test_visibility_filters_pagination_and_order(uow_factory, organizer):
    other = make_user(Role.ORGANIZER)
    async with uow_factory() as uow:
        await uow.users.add(other)
        await uow.commit()
    await _save(
        uow_factory,
        make_event(
            organizer.id, name="B", status=EventStatus.PUBLISHED, starts_in=timedelta(days=2)
        ),
        make_event(
            organizer.id, name="A", status=EventStatus.PUBLISHED, starts_in=timedelta(days=1)
        ),
        make_event(organizer.id, name="Borrador"),
        make_event(
            other.id, name="Ajeno", status=EventStatus.PUBLISHED, starts_in=timedelta(days=3)
        ),
    )

    public, public_total = await _search(uow_factory, exclude_drafts=True, limit=2)
    mine, _ = await _search(uow_factory, organizer_id=organizer.id)

    assert [e.name for e in public] == ["A", "B"]
    assert public_total == 3
    assert {e.name for e in mine} == {"A", "B", "Borrador"}


async def test_delete_event(uow_factory, organizer):
    event = make_event(organizer.id)
    await _save(uow_factory, event)
    async with uow_factory() as uow:
        await uow.events.delete(event.id)
        await uow.commit()
    async with uow_factory() as uow:
        assert await uow.events.get(event.id) is None


@pytest.mark.parametrize(
    "sql",
    [
        # capacidad inválida
        "UPDATE events SET capacity = 0",
        # fin antes del inicio
        "UPDATE events SET end_at = start_at - interval '1 hour'",
        # más inscritos que capacidad
        "UPDATE events SET registered_count = capacity + 1",
        # estado desconocido
        "UPDATE events SET status = 'archived'",
        # finalizado sin datos de cierre
        "UPDATE events SET status = 'finished'",
        # datos de cierre en un borrador
        "UPDATE events SET closed_at = now(), closed_source = 'manual', "
        "closed_by_id = organizer_id",
        # cierre automático con usuario / manual sin usuario
        "UPDATE events SET status = 'finished', closed_at = now(), "
        "closed_source = 'scheduler', closed_by_id = organizer_id",
        "UPDATE events SET status = 'finished', closed_at = now(), "
        "closed_source = 'manual', closed_by_id = NULL",
    ],
)
async def test_database_enforces_event_invariants(uow_factory, organizer, engine, sql):
    await _save(uow_factory, make_event(organizer.id))

    async with engine.connect() as connection:
        with pytest.raises(IntegrityError, match="violates check constraint"):
            await connection.execute(text(sql))


async def test_scheduler_closing_is_valid_without_a_user(uow_factory, organizer, engine):
    await _save(uow_factory, make_event(organizer.id, status=EventStatus.PUBLISHED))

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE events SET status = 'finished', closed_at = now(), "
                "closed_source = 'scheduler', closed_by_id = NULL"
            )
        )


async def test_users_with_events_cannot_be_deleted(uow_factory, organizer, engine):
    await _save(uow_factory, make_event(organizer.id))
    async with engine.connect() as connection:
        with pytest.raises(IntegrityError, match="foreign key"):
            await connection.execute(text("DELETE FROM users"))


async def test_name_search_uses_the_trigram_index(engine):
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_events_name_trgm'")
            )
        ).all()
    assert rows and "gin_trgm_ops" in rows[0][0]


async def test_speakers_crud_and_search(uow_factory, organizer):
    ana, luis = make_speaker(organizer.id, "Ana López"), make_speaker(organizer.id, "Luis")
    async with uow_factory() as uow:
        await uow.speakers.add(ana)
        await uow.speakers.add(luis)
        await uow.commit()

    async with uow_factory() as uow:
        found, total = await uow.speakers.list_page("ANA", 10, 0)
        assert (total, [s.name for s in found]) == (1, ["Ana López"])
        ana.bio = "Nueva bio"
        await uow.speakers.update(ana)
        await uow.speakers.delete(luis.id)
        await uow.commit()

    async with uow_factory() as uow:
        assert (await uow.speakers.get(ana.id)).bio == "Nueva bio"
        assert await uow.speakers.get(luis.id) is None


async def test_user_list_filters_by_email_or_name_and_update(uow_factory):
    ana = make_user(email="ana@example.com")
    luis = make_user(email="luis@example.com")
    async with uow_factory() as uow:
        await uow.users.add(ana)
        await uow.users.add(luis)
        await uow.commit()

    async with uow_factory() as uow:
        users, total = await uow.users.list_page("ANA@", 10, 0)
        assert (total, [u.email for u in users]) == (1, ["ana@example.com"])
        ana.role, ana.is_active = Role.ORGANIZER, False
        await uow.users.update(ana)
        await uow.commit()

    async with uow_factory() as uow:
        stored = await uow.users.get_by_id(ana.id)
    assert (stored.role, stored.is_active) == (Role.ORGANIZER, False)
