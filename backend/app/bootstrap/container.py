from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.adapters.outbound.cache.redis_client import RedisHealthProbe, create_redis
from app.adapters.outbound.persistence.database import create_engine, create_session_factory
from app.adapters.outbound.persistence.health import SqlHealthProbe
from app.adapters.outbound.persistence.unit_of_work import SqlUnitOfWork
from app.adapters.outbound.security.argon2_hasher import Argon2PasswordHasher
from app.adapters.outbound.security.jwt_token_service import JwtTokenService
from app.adapters.outbound.system.system_clock import SystemClock
from app.application.ports.inbound.admin import EnsureAdminUser, ListUsers, UpdateUser
from app.application.ports.inbound.auth import GetCurrentUser, LoginUser, RegisterUser
from app.application.ports.inbound.events import (
    CancelEvent,
    CreateEvent,
    DeleteEvent,
    FinishEvent,
    GetEvent,
    PublishEvent,
    SearchEvents,
    UpdateEvent,
)
from app.application.ports.inbound.health import CheckReadiness
from app.application.ports.inbound.speakers import (
    CreateSpeaker,
    DeleteSpeaker,
    GetSpeaker,
    ListSpeakers,
    UpdateSpeaker,
)
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.health import HealthProbe
from app.application.ports.outbound.security import PasswordHasher, TokenService
from app.application.ports.outbound.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.use_cases.admin.ensure_admin_user import EnsureAdminUserUseCase
from app.application.use_cases.admin.manage_users import ListUsersUseCase, UpdateUserUseCase
from app.application.use_cases.auth.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
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
from app.application.use_cases.health.check_readiness import CheckReadinessUseCase
from app.application.use_cases.speakers.manage_speakers import (
    CreateSpeakerUseCase,
    DeleteSpeakerUseCase,
    GetSpeakerUseCase,
    ListSpeakersUseCase,
    UpdateSpeakerUseCase,
)
from app.bootstrap.settings import Settings


@dataclass
class Container:
    """Casos de uso ya cableados. Los adaptadores HTTP y de tareas solo ven esta fachada."""

    register_user: RegisterUser
    login_user: LoginUser
    get_current_user: GetCurrentUser
    ensure_admin: EnsureAdminUser
    check_readiness: CheckReadiness
    create_event: CreateEvent
    update_event: UpdateEvent
    get_event: GetEvent
    search_events: SearchEvents
    delete_event: DeleteEvent
    publish_event: PublishEvent
    finish_event: FinishEvent
    cancel_event: CancelEvent
    create_speaker: CreateSpeaker
    update_speaker: UpdateSpeaker
    delete_speaker: DeleteSpeaker
    get_speaker: GetSpeaker
    list_speakers: ListSpeakers
    list_users: ListUsers
    update_user: UpdateUser
    _closers: list[Callable[[], Awaitable[None]]] = field(default_factory=list)

    async def aclose(self) -> None:
        for closer in reversed(self._closers):
            await closer()


def wire_use_cases(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    hasher: PasswordHasher,
    tokens: TokenService,
    probes: list[HealthProbe],
    closers: list[Callable[[], Awaitable[None]]] | None = None,
) -> Container:
    """Conecta los casos de uso con sus puertos. Lo usan build_container y los tests."""
    return Container(
        register_user=RegisterUserUseCase(uow_factory, hasher, clock),
        login_user=LoginUserUseCase(uow_factory, hasher, tokens),
        get_current_user=GetCurrentUserUseCase(uow_factory, tokens),
        ensure_admin=EnsureAdminUserUseCase(uow_factory, hasher, clock),
        check_readiness=CheckReadinessUseCase(probes),
        create_event=CreateEventUseCase(uow_factory, clock),
        update_event=UpdateEventUseCase(uow_factory, clock),
        get_event=GetEventUseCase(uow_factory, clock),
        search_events=SearchEventsUseCase(uow_factory, clock),
        delete_event=DeleteEventUseCase(uow_factory),
        publish_event=PublishEventUseCase(uow_factory, clock),
        finish_event=FinishEventUseCase(uow_factory, clock),
        cancel_event=CancelEventUseCase(uow_factory, clock),
        create_speaker=CreateSpeakerUseCase(uow_factory, clock),
        update_speaker=UpdateSpeakerUseCase(uow_factory),
        delete_speaker=DeleteSpeakerUseCase(uow_factory),
        get_speaker=GetSpeakerUseCase(uow_factory),
        list_speakers=ListSpeakersUseCase(uow_factory),
        list_users=ListUsersUseCase(uow_factory),
        update_user=UpdateUserUseCase(uow_factory),
        _closers=closers or [],
    )


def build_container(settings: Settings) -> Container:
    """Único lugar que instancia adaptadores concretos y los inyecta en los casos de uso."""
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis = create_redis(settings.redis_url)

    def uow_factory() -> UnitOfWork:
        return SqlUnitOfWork(session_factory)

    clock = SystemClock()
    return wire_use_cases(
        uow_factory=uow_factory,
        clock=clock,
        hasher=Argon2PasswordHasher(),
        tokens=JwtTokenService(settings.jwt_secret, settings.jwt_expire_minutes, clock),
        probes=[SqlHealthProbe(engine), RedisHealthProbe(redis)],
        closers=[engine.dispose, redis.aclose],
    )
