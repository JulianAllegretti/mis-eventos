from uuid import UUID

from app.bootstrap.container import Container, wire_use_cases
from app.domain.models.event import Event
from app.domain.models.speaker import Speaker
from app.domain.models.user import User
from tests.fakes.in_memory import (
    FakePasswordHasher,
    FakeTokenService,
    FixedClock,
    StaticProbe,
    make_uow_factory,
)


def build_fake_container(
    users_store: dict[UUID, User] | None = None,
    events_store: dict[UUID, Event] | None = None,
    speakers_store: dict[UUID, Speaker] | None = None,
    *,
    clock: FixedClock | None = None,
    postgres_ok: bool = True,
    redis_ok: bool = True,
) -> Container:
    users = users_store if users_store is not None else {}
    probes = [StaticProbe("postgres", postgres_ok, True), StaticProbe("redis", redis_ok, False)]
    return wire_use_cases(
        uow_factory=make_uow_factory(users, events_store, speakers_store),
        clock=clock or FixedClock(),
        hasher=FakePasswordHasher(),
        tokens=FakeTokenService(),
        probes=probes,
    )
