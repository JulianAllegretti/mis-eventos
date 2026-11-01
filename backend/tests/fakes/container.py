from uuid import UUID

from app.application.dto.policies import LoginRateLimit
from app.bootstrap.container import Container, wire_use_cases
from app.domain.models.event import Event
from app.domain.models.speaker import Speaker
from app.domain.models.user import User
from tests.fakes.in_memory import (
    FakeCache,
    FakeMetrics,
    FakePasswordHasher,
    FakeRateLimiter,
    FakeSlotCounter,
    FakeTokenService,
    FixedClock,
    StaticProbe,
    Stores,
    make_stores,
)


def build_fake_container(
    users_store: dict[UUID, User] | None = None,
    events_store: dict[UUID, Event] | None = None,
    speakers_store: dict[UUID, Speaker] | None = None,
    *,
    stores: Stores | None = None,
    clock: FixedClock | None = None,
    slots: FakeSlotCounter | None = None,
    cache: FakeCache | None = None,
    metrics: FakeMetrics | None = None,
    limiter: FakeRateLimiter | None = None,
    login_policy: LoginRateLimit | None = None,
    postgres_ok: bool = True,
    redis_ok: bool = True,
) -> Container:
    shared = stores or make_stores(users_store, events_store, speakers_store)
    probes = [StaticProbe("postgres", postgres_ok, True), StaticProbe("redis", redis_ok, False)]
    # Importación local para no crear un ciclo con in_memory.
    from tests.fakes.in_memory import InMemoryUnitOfWork

    return wire_use_cases(
        uow_factory=lambda: InMemoryUnitOfWork(shared),
        clock=clock or FixedClock(),
        hasher=FakePasswordHasher(),
        tokens=FakeTokenService(),
        probes=probes,
        slots=slots or FakeSlotCounter(),
        cache=cache or FakeCache(),
        metrics=metrics or FakeMetrics(),
        limiter=limiter or FakeRateLimiter(),
        login_policy=login_policy,
    )
