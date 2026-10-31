"""Implementaciones en memoria de los puertos outbound, para tests sin I/O."""

import copy
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

from app.application.dto.queries import EventSearchCriteria
from app.application.ports.outbound.cache import CacheLookup
from app.application.ports.outbound.security import TokenClaims
from app.application.ports.outbound.slot_counter import SlotResult
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import AlreadyRegistered, EmailAlreadyRegistered, ScheduleConflict
from app.domain.models.event import ClosedSource, Event, EventStatus
from app.domain.models.registration import Registration, SessionRegistration
from app.domain.models.session import Session
from app.domain.models.speaker import Speaker
from app.domain.models.user import Role, User

FIXED_NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@dataclass
class Stores:
    """Estado compartido entre todas las unidades de trabajo de una prueba."""

    users: dict[UUID, User] = field(default_factory=dict)
    events: dict[UUID, Event] = field(default_factory=dict)
    speakers: dict[UUID, Speaker] = field(default_factory=dict)
    sessions: dict[UUID, Session] = field(default_factory=dict)
    registrations: dict[UUID, Registration] = field(default_factory=dict)
    session_registrations: dict[UUID, SessionRegistration] = field(default_factory=dict)


class InMemoryUserRepository:
    def __init__(self, stores: Stores) -> None:
        self._store = stores.users

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._store.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    async def add(self, user: User) -> None:
        if await self.get_by_email(user.email) is not None:
            raise EmailAlreadyRegistered()
        self._store[user.id] = user

    async def update(self, user: User) -> None:
        self._store[user.id] = user

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[User], int]:
        needle = (q or "").lower()
        matches = sorted(
            (
                u
                for u in self._store.values()
                if needle in u.email.lower() or needle in u.full_name.lower()
            ),
            key=lambda u: (u.created_at, u.id),
        )
        return matches[offset : offset + limit], len(matches)


class InMemoryEventRepository:
    def __init__(self, stores: Stores) -> None:
        self._store = stores.events

    async def get(self, event_id: UUID) -> Event | None:
        return self._store.get(event_id)

    async def add(self, event: Event) -> None:
        self._store[event.id] = event

    async def update(self, event: Event) -> None:
        self._store[event.id] = event

    async def delete(self, event_id: UUID) -> None:
        self._store.pop(event_id, None)

    async def search(self, criteria: EventSearchCriteria) -> tuple[list[Event], int]:
        needle = (criteria.q or "").lower()
        matches = [
            e
            for e in self._store.values()
            if needle in e.name.lower()
            and (criteria.organizer_id is None or e.organizer_id == criteria.organizer_id)
            and not (criteria.exclude_drafts and e.status is EventStatus.DRAFT)
            and (criteria.status is None or e.effective_status(criteria.now) is criteria.status)
        ]
        matches.sort(key=lambda e: (e.start_at, e.id))
        return matches[criteria.offset : criteria.offset + criteria.limit], len(matches)

    async def try_increment_registered(self, event_id: UUID, now: datetime) -> bool:
        event = self._store.get(event_id)
        if (
            event is None
            or event.registered_count >= event.capacity
            or event.status is not EventStatus.PUBLISHED
            or event.end_at < now
        ):
            return False
        event.registered_count += 1
        return True

    async def decrement_registered(self, event_id: UUID) -> None:
        event = self._store.get(event_id)
        if event is not None and event.registered_count > 0:
            event.registered_count -= 1

    async def finish_expired(self, now: datetime) -> list[UUID]:
        closed = []
        for event in self._store.values():
            if event.status is EventStatus.PUBLISHED and event.end_at < now:
                event.status = EventStatus.FINISHED
                event.closed_at = event.updated_at = now
                event.closed_by_id = None
                event.closed_source = ClosedSource.SCHEDULER
                closed.append(event.id)
        return closed

    async def list_open_availability(self, now: datetime) -> list[tuple[UUID, int]]:
        return [
            (e.id, e.available_slots)
            for e in self._store.values()
            if e.status is EventStatus.PUBLISHED and e.end_at >= now
        ]


class InMemorySpeakerRepository:
    def __init__(self, stores: Stores) -> None:
        self._store = stores.speakers

    async def get(self, speaker_id: UUID) -> Speaker | None:
        return self._store.get(speaker_id)

    async def get_many(self, speaker_ids: list[UUID]) -> list[Speaker]:
        return [self._store[i] for i in speaker_ids if i in self._store]

    async def add(self, speaker: Speaker) -> None:
        self._store[speaker.id] = speaker

    async def update(self, speaker: Speaker) -> None:
        self._store[speaker.id] = speaker

    async def delete(self, speaker_id: UUID) -> None:
        self._store.pop(speaker_id, None)

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[Speaker], int]:
        needle = (q or "").lower()
        matches = sorted(
            (s for s in self._store.values() if needle in s.name.lower()),
            key=lambda s: (s.name, s.id),
        )
        return matches[offset : offset + limit], len(matches)


class InMemorySessionRepository:
    def __init__(self, stores: Stores) -> None:
        self._store = stores.sessions

    async def get(self, session_id: UUID) -> Session | None:
        return self._store.get(session_id)

    async def add(self, session: Session) -> None:
        await self._ensure_no_overlap(session)
        self._store[session.id] = session

    async def update(self, session: Session) -> None:
        await self._ensure_no_overlap(session)
        self._store[session.id] = session

    async def delete(self, session_id: UUID) -> None:
        self._store.pop(session_id, None)

    async def list_for_event(self, event_id: UUID) -> list[Session]:
        return [s for s in self._store.values() if s.event_id == event_id]

    async def count_for_speaker(self, speaker_id: UUID) -> int:
        return sum(1 for s in self._store.values() if s.speaker_id == speaker_id)

    async def speaker_has_overlap(
        self, speaker_id: UUID, start_at: datetime, end_at: datetime, exclude_id: UUID | None
    ) -> bool:
        return any(
            s.speaker_id == speaker_id
            and s.id != exclude_id
            and s.start_at < end_at
            and s.end_at > start_at
            for s in self._store.values()
        )

    async def try_increment_registered(self, session_id: UUID) -> bool:
        session = self._store.get(session_id)
        if session is None or session.registered_count >= session.capacity:
            return False
        session.registered_count += 1
        return True

    async def decrement_registered(self, session_id: UUID) -> None:
        session = self._store.get(session_id)
        if session is not None and session.registered_count > 0:
            session.registered_count -= 1

    async def _ensure_no_overlap(self, session: Session) -> None:
        # Imita la restricción EXCLUDE de PostgreSQL.
        if await self.speaker_has_overlap(
            session.speaker_id, session.start_at, session.end_at, session.id
        ):
            raise ScheduleConflict("El ponente ya tiene una sesión en ese horario")


class InMemoryRegistrationRepository:
    def __init__(self, stores: Stores) -> None:
        self._stores = stores

    @property
    def _store(self) -> dict[UUID, Registration]:
        return self._stores.registrations

    async def get_active(self, user_id: UUID, event_id: UUID) -> Registration | None:
        return next(
            (
                r
                for r in self._store.values()
                if r.user_id == user_id and r.event_id == event_id and r.cancelled_at is None
            ),
            None,
        )

    async def add(self, registration: Registration) -> None:
        if await self.get_active(registration.user_id, registration.event_id) is not None:
            raise AlreadyRegistered("Ya estás inscrito en este evento")
        self._store[registration.id] = registration

    async def cancel(self, user_id: UUID, event_id: UUID, now: datetime) -> bool:
        registration = await self.get_active(user_id, event_id)
        if registration is None:
            return False
        registration.cancelled_at = now
        return True

    async def exists_for_event(self, event_id: UUID) -> bool:
        return any(r.event_id == event_id for r in self._store.values())

    async def list_active_for_user(self, user_id: UUID) -> list[tuple[Registration, Event]]:
        pairs = [
            (r, self._stores.events[r.event_id])
            for r in self._store.values()
            if r.user_id == user_id and r.cancelled_at is None
        ]
        return sorted(pairs, key=lambda p: (p[1].start_at, p[1].id))

    async def list_attendees(
        self, event_id: UUID, limit: int, offset: int
    ) -> tuple[list[tuple[Registration, User]], int]:
        rows = sorted(
            (
                (r, self._stores.users[r.user_id])
                for r in self._store.values()
                if r.event_id == event_id and r.cancelled_at is None
            ),
            key=lambda p: (p[0].created_at, p[0].id),
        )
        return rows[offset : offset + limit], len(rows)


class InMemorySessionRegistrationRepository:
    def __init__(self, stores: Stores) -> None:
        self._stores = stores

    @property
    def _store(self) -> dict[UUID, SessionRegistration]:
        return self._stores.session_registrations

    async def lock_user(self, user_id: UUID) -> None:
        return None

    async def get_active(self, user_id: UUID, session_id: UUID) -> SessionRegistration | None:
        return next(
            (
                r
                for r in self._store.values()
                if r.user_id == user_id and r.session_id == session_id and r.cancelled_at is None
            ),
            None,
        )

    async def add(self, registration: SessionRegistration) -> None:
        if await self.get_active(registration.user_id, registration.session_id) is not None:
            raise AlreadyRegistered("Ya estás inscrito en esta sesión")
        self._store[registration.id] = registration

    async def cancel(self, user_id: UUID, session_id: UUID, now: datetime) -> bool:
        registration = await self.get_active(user_id, session_id)
        if registration is None:
            return False
        registration.cancelled_at = now
        return True

    async def cancel_all_for_event(
        self, user_id: UUID, event_id: UUID, now: datetime
    ) -> list[UUID]:
        cancelled = []
        for registration in self._store.values():
            session = self._stores.sessions.get(registration.session_id)
            if (
                registration.user_id == user_id
                and registration.cancelled_at is None
                and session is not None
                and session.event_id == event_id
            ):
                registration.cancelled_at = now
                cancelled.append(session.id)
        return cancelled

    async def has_overlap(self, user_id: UUID, start_at: datetime, end_at: datetime) -> bool:
        for registration in self._store.values():
            session = self._stores.sessions.get(registration.session_id)
            if (
                registration.user_id == user_id
                and registration.cancelled_at is None
                and session is not None
                and session.start_at < end_at
                and session.end_at > start_at
            ):
                return True
        return False

    async def list_active_for_user(
        self, user_id: UUID
    ) -> list[tuple[SessionRegistration, Session]]:
        return [
            (r, self._stores.sessions[r.session_id])
            for r in self._store.values()
            if r.user_id == user_id and r.cancelled_at is None
        ]


class InMemoryUnitOfWork:
    """Emula la transacción: si se sale sin commit, el estado vuelve al de la entrada.

    Los objetos se restauran en su sitio (no se reemplazan) para que las referencias que
    las pruebas conservan sigan apuntando a las mismas entidades.
    """

    def __init__(self, stores: Stores) -> None:
        self._stores = stores
        self._snapshot: list[tuple[dict, dict]] = []
        self.users = InMemoryUserRepository(stores)
        self.events = InMemoryEventRepository(stores)
        self.speakers = InMemorySpeakerRepository(stores)
        self.sessions = InMemorySessionRepository(stores)
        self.registrations = InMemoryRegistrationRepository(stores)
        self.session_registrations = InMemorySessionRegistrationRepository(stores)
        self.committed = False

    async def __aenter__(self) -> Self:
        self._snapshot = [
            ({key: (obj, copy.copy(obj)) for key, obj in store.items()}, store)
            for store in vars(self._stores).values()
        ]
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        for saved, store in self._snapshot:
            store.clear()
            for key, (obj, original) in saved.items():
                for f in fields(obj):
                    setattr(obj, f.name, getattr(original, f.name))
                store[key] = obj


def make_stores(
    users: dict[UUID, User] | None = None,
    events: dict[UUID, Event] | None = None,
    speakers: dict[UUID, Speaker] | None = None,
    *,
    sessions: dict[UUID, Session] | None = None,
    registrations: dict[UUID, Registration] | None = None,
    session_registrations: dict[UUID, SessionRegistration] | None = None,
) -> Stores:
    """Crea los almacenes reutilizando los diccionarios que la prueba ya tenga."""
    return Stores(
        users=users if users is not None else {},
        events=events if events is not None else {},
        speakers=speakers if speakers is not None else {},
        sessions=sessions if sessions is not None else {},
        registrations=registrations if registrations is not None else {},
        session_registrations=(session_registrations if session_registrations is not None else {}),
    )


def make_uow_factory(
    users_store: dict[UUID, User],
    events_store: dict[UUID, Event] | None = None,
    speakers_store: dict[UUID, Speaker] | None = None,
    *,
    sessions: dict[UUID, Session] | None = None,
    registrations: dict[UUID, Registration] | None = None,
    session_registrations: dict[UUID, SessionRegistration] | None = None,
) -> UnitOfWorkFactory:
    stores = make_stores(
        users_store,
        events_store,
        speakers_store,
        sessions=sessions,
        registrations=registrations,
        session_registrations=session_registrations,
    )
    return lambda: InMemoryUnitOfWork(stores)


class FakePasswordHasher:
    async def hash(self, password: str) -> str:
        return f"hashed:{password}"

    async def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokenService:
    ttl_seconds = 3600

    def issue(self, user: User) -> str:
        return f"token:{user.id}:{user.role.value}"

    def decode(self, token: str) -> TokenClaims | None:
        parts = token.split(":")
        if len(parts) != 3 or parts[0] != "token":
            return None
        try:
            return TokenClaims(user_id=UUID(parts[1]), role=Role(parts[2]))
        except ValueError:
            return None


class FixedClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class StaticProbe:
    def __init__(self, name: str, ok: bool, critical: bool) -> None:
        self.name = name
        self.critical = critical
        self._ok = ok

    async def check(self) -> bool:
        return self._ok


class FakeSlotCounter:
    """Contador de cupos en memoria con la misma semántica que el de Redis."""

    def __init__(self, *, available: bool = True) -> None:
        self.counters: dict[UUID, int] = {}
        self.claims: set[tuple[UUID, UUID]] = set()
        self.available = available
        self.calls: list[tuple[str, UUID]] = []

    async def claim(self, event_id: UUID, user_id: UUID) -> bool:
        self.calls.append(("claim", event_id))
        if not self.available:
            return True
        if (event_id, user_id) in self.claims:
            return False
        self.claims.add((event_id, user_id))
        return True

    async def unclaim(self, event_id: UUID, user_id: UUID) -> None:
        self.calls.append(("unclaim", event_id))
        self.claims.discard((event_id, user_id))

    async def try_acquire(self, event_id: UUID) -> SlotResult:
        self.calls.append(("acquire", event_id))
        if not self.available:
            return SlotResult.BYPASSED
        if event_id not in self.counters:
            return SlotResult.MISSING
        if self.counters[event_id] <= 0:
            return SlotResult.FULL
        self.counters[event_id] -= 1
        return SlotResult.ALLOWED

    async def release(self, event_id: UUID) -> None:
        self.calls.append(("release", event_id))
        if event_id in self.counters:
            self.counters[event_id] += 1

    async def initialize(self, event_id: UUID, available: int) -> None:
        self.calls.append(("initialize", event_id))
        self.counters.setdefault(event_id, max(0, available))

    async def reconcile(self, event_id: UUID, available: int) -> None:
        self.calls.append(("reconcile", event_id))
        if event_id in self.counters:
            self.counters[event_id] = max(0, available)

    async def invalidate(self, event_id: UUID) -> None:
        self.calls.append(("invalidate", event_id))
        self.counters.pop(event_id, None)


class FakeCache:
    """Caché en memoria con grupos versionados, igual que la de Redis."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], str] = {}
        self.versions: dict[str, int] = {}
        self.hits = 0
        self.misses = 0

    async def get(self, group: str, key: str) -> CacheLookup:
        version = str(self.versions.get(group, 0))
        value = self.values.get((group, version, key))
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return CacheLookup(value=value, version=version)

    async def set(self, group: str, key: str, version: str, value: str, ttl_seconds: int) -> None:
        self.values[(group, version, key)] = value

    async def invalidate_group(self, group: str) -> None:
        self.versions[group] = self.versions.get(group, 0) + 1
