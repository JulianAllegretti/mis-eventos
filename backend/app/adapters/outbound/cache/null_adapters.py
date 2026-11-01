"""Implementaciones que no hacen nada, para ejecutar sin Redis (REDIS_URL vacío) o en pruebas."""

from uuid import UUID

from app.application.ports.outbound.cache import CacheLookup
from app.application.ports.outbound.slot_counter import SlotResult


class NullSlotCounter:
    async def claim(self, event_id: UUID, user_id: UUID) -> bool:
        return True

    async def unclaim(self, event_id: UUID, user_id: UUID) -> None:
        return None

    async def try_acquire(self, event_id: UUID) -> SlotResult:
        return SlotResult.BYPASSED

    async def release(self, event_id: UUID) -> None:
        return None

    async def initialize(self, event_id: UUID, available: int) -> None:
        return None

    async def reconcile(self, event_id: UUID, available: int) -> None:
        return None

    async def invalidate(self, event_id: UUID) -> None:
        return None


class NullCache:
    async def get(self, group: str, key: str) -> CacheLookup:
        return CacheLookup(value=None, version="0")

    async def set(self, group: str, key: str, version: str, value: str, ttl_seconds: int) -> None:
        return None

    async def invalidate_group(self, group: str) -> None:
        return None


class NullRateLimiter:
    async def retry_after(self, key: str, limit: int) -> int:
        return 0

    async def record_failure(self, key: str, window_seconds: int) -> None:
        return None

    async def reset(self, key: str) -> None:
        return None
