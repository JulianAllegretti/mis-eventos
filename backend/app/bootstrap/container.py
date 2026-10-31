from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.adapters.outbound.cache.null_adapters import NullCache, NullSlotCounter
from app.adapters.outbound.cache.redis_cache import RedisCache
from app.adapters.outbound.cache.redis_client import RedisHealthProbe, create_redis
from app.adapters.outbound.cache.redis_slot_counter import RedisSlotCounter
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
from app.application.ports.inbound.maintenance import FinishExpiredEvents, ReconcileSlots
from app.application.ports.inbound.registrations import (
    CancelEventRegistration,
    CancelSessionRegistration,
    ListEventAttendees,
    ListMyRegistrations,
    RegisterToEvent,
    RegisterToSession,
)
from app.application.ports.inbound.sessions import (
    CreateSession,
    DeleteSession,
    ListEventSessions,
    UpdateSession,
)
from app.application.ports.inbound.speakers import (
    CreateSpeaker,
    DeleteSpeaker,
    GetSpeaker,
    ListSpeakers,
    UpdateSpeaker,
)
from app.application.ports.outbound.cache import Cache
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.health import HealthProbe
from app.application.ports.outbound.security import PasswordHasher, TokenService
from app.application.ports.outbound.slot_counter import SlotCounter
from app.application.ports.outbound.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.event_sync import EventSync
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
from app.application.use_cases.events.maintenance import (
    FinishExpiredEventsUseCase,
    ReconcileSlotsUseCase,
)
from app.application.use_cases.events.search_events import SearchEventsUseCase
from app.application.use_cases.events.update_event import UpdateEventUseCase
from app.application.use_cases.health.check_readiness import CheckReadinessUseCase
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
from app.application.use_cases.sessions.manage_sessions import (
    CreateSessionUseCase,
    DeleteSessionUseCase,
    ListEventSessionsUseCase,
    UpdateSessionUseCase,
)
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
    create_session: CreateSession
    update_session: UpdateSession
    delete_session: DeleteSession
    list_event_sessions: ListEventSessions
    register_to_event: RegisterToEvent
    cancel_event_registration: CancelEventRegistration
    list_my_registrations: ListMyRegistrations
    list_event_attendees: ListEventAttendees
    register_to_session: RegisterToSession
    cancel_session_registration: CancelSessionRegistration
    finish_expired_events: FinishExpiredEvents
    reconcile_slots: ReconcileSlots
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
    slots: SlotCounter,
    cache: Cache,
    cache_ttl_seconds: int = 60,
    closers: list[Callable[[], Awaitable[None]]] | None = None,
) -> Container:
    """Conecta los casos de uso con sus puertos. Lo usan build_container y los tests."""
    sync = EventSync(cache, slots)
    return Container(
        register_user=RegisterUserUseCase(uow_factory, hasher, clock),
        login_user=LoginUserUseCase(uow_factory, hasher, tokens),
        get_current_user=GetCurrentUserUseCase(uow_factory, tokens),
        ensure_admin=EnsureAdminUserUseCase(uow_factory, hasher, clock),
        check_readiness=CheckReadinessUseCase(probes),
        create_event=CreateEventUseCase(uow_factory, clock),
        update_event=UpdateEventUseCase(uow_factory, clock, sync),
        get_event=GetEventUseCase(uow_factory, clock, cache, cache_ttl_seconds),
        search_events=SearchEventsUseCase(uow_factory, clock, cache, cache_ttl_seconds),
        delete_event=DeleteEventUseCase(uow_factory, sync),
        publish_event=PublishEventUseCase(uow_factory, clock, sync),
        finish_event=FinishEventUseCase(uow_factory, clock, sync),
        cancel_event=CancelEventUseCase(uow_factory, clock, sync),
        create_speaker=CreateSpeakerUseCase(uow_factory, clock),
        update_speaker=UpdateSpeakerUseCase(uow_factory),
        delete_speaker=DeleteSpeakerUseCase(uow_factory),
        get_speaker=GetSpeakerUseCase(uow_factory),
        list_speakers=ListSpeakersUseCase(uow_factory),
        list_users=ListUsersUseCase(uow_factory),
        update_user=UpdateUserUseCase(uow_factory),
        create_session=CreateSessionUseCase(uow_factory, clock, sync),
        update_session=UpdateSessionUseCase(uow_factory, clock, sync),
        delete_session=DeleteSessionUseCase(uow_factory, clock, sync),
        list_event_sessions=ListEventSessionsUseCase(uow_factory),
        register_to_event=RegisterToEventUseCase(uow_factory, clock, slots, sync),
        cancel_event_registration=CancelEventRegistrationUseCase(uow_factory, clock, slots, sync),
        list_my_registrations=ListMyRegistrationsUseCase(uow_factory),
        list_event_attendees=ListEventAttendeesUseCase(uow_factory),
        register_to_session=RegisterToSessionUseCase(uow_factory, clock, sync),
        cancel_session_registration=CancelSessionRegistrationUseCase(uow_factory, clock, sync),
        finish_expired_events=FinishExpiredEventsUseCase(uow_factory, clock, slots, sync),
        reconcile_slots=ReconcileSlotsUseCase(uow_factory, clock, slots),
        _closers=closers or [],
    )


def build_container(settings: Settings) -> Container:
    """Único lugar que instancia adaptadores concretos y los inyecta en los casos de uso."""
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    def uow_factory() -> UnitOfWork:
        return SqlUnitOfWork(session_factory)

    probes: list[HealthProbe] = [SqlHealthProbe(engine)]
    closers: list[Callable[[], Awaitable[None]]] = [engine.dispose]
    slots: SlotCounter = NullSlotCounter()
    cache: Cache = NullCache()
    if settings.redis_url:
        redis = create_redis(settings.redis_url)
        slots, cache = RedisSlotCounter(redis), RedisCache(redis)
        probes.append(RedisHealthProbe(redis))
        closers.append(redis.aclose)

    clock = SystemClock()
    return wire_use_cases(
        uow_factory=uow_factory,
        clock=clock,
        hasher=Argon2PasswordHasher(),
        tokens=JwtTokenService(settings.jwt_secret, settings.jwt_expire_minutes, clock),
        probes=probes,
        slots=slots,
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        closers=closers,
    )
