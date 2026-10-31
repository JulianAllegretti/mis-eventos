"""Implementaciones en memoria de los puertos outbound, para tests sin I/O."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

from app.application.dto.queries import EventSearchCriteria
from app.application.ports.outbound.security import TokenClaims
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import EmailAlreadyRegistered
from app.domain.models.event import Event, EventStatus
from app.domain.models.speaker import Speaker
from app.domain.models.user import Role, User

FIXED_NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class InMemoryUserRepository:
    def __init__(self, store: dict[UUID, User]) -> None:
        self._store = store

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
    def __init__(self, store: dict[UUID, Event]) -> None:
        self._store = store

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


class InMemorySpeakerRepository:
    def __init__(self, store: dict[UUID, Speaker]) -> None:
        self._store = store

    async def get(self, speaker_id: UUID) -> Speaker | None:
        return self._store.get(speaker_id)

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


class InMemoryUnitOfWork:
    def __init__(
        self,
        users_store: dict[UUID, User],
        events_store: dict[UUID, Event],
        speakers_store: dict[UUID, Speaker],
    ) -> None:
        self.users = InMemoryUserRepository(users_store)
        self.events = InMemoryEventRepository(events_store)
        self.speakers = InMemorySpeakerRepository(speakers_store)
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


def make_uow_factory(
    users_store: dict[UUID, User],
    events_store: dict[UUID, Event] | None = None,
    speakers_store: dict[UUID, Speaker] | None = None,
) -> UnitOfWorkFactory:
    events = events_store if events_store is not None else {}
    speakers = speakers_store if speakers_store is not None else {}
    return lambda: InMemoryUnitOfWork(users_store, events, speakers)


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
