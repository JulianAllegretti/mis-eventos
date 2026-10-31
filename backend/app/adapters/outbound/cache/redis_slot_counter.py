from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.outbound.slot_counter import SlotResult

log = structlog.get_logger()

COUNTER_TTL_SECONDS = 24 * 60 * 60
CLAIM_TTL_SECONDS = 10  # cubre el vuelo de una inscripción; después decide la restricción única

# Todos los scripts son atómicos en Redis: no hay ventana entre leer y escribir el contador.
_ACQUIRE = """
local value = redis.call('GET', KEYS[1])
if not value then return -2 end
if tonumber(value) <= 0 then return -1 end
redis.call('DECR', KEYS[1])
return 1
"""
_RELEASE = """
if redis.call('EXISTS', KEYS[1]) == 1 then return redis.call('INCR', KEYS[1]) end
return nil
"""
_RECONCILE = """
if redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('SET', KEYS[1], ARGV[1], 'KEEPTTL')
  return 1
end
return 0
"""

_RESULT_BY_CODE = {1: SlotResult.ALLOWED, -1: SlotResult.FULL, -2: SlotResult.MISSING}


class RedisSlotCounter:
    """Filtro previo de cupos (ADR 0005). Si Redis falla, devuelve BYPASSED y decide PostgreSQL."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._acquire = client.register_script(_ACQUIRE)
        self._release = client.register_script(_RELEASE)
        self._reconcile = client.register_script(_RECONCILE)

    @staticmethod
    def _key(event_id: UUID) -> str:
        return f"slots:event:{event_id}"

    @staticmethod
    def _claim_key(event_id: UUID, user_id: UUID) -> str:
        return f"claim:event:{event_id}:user:{user_id}"

    async def claim(self, event_id: UUID, user_id: UUID) -> bool:
        try:
            return bool(
                await self._client.set(
                    self._claim_key(event_id, user_id), "1", nx=True, ex=CLAIM_TTL_SECONDS
                )
            )
        except (RedisError, OSError) as exc:
            self._warn("claim", exc)
            return True  # sin Redis no hay candado: decide la restricción única de PostgreSQL

    async def unclaim(self, event_id: UUID, user_id: UUID) -> None:
        try:
            await self._client.delete(self._claim_key(event_id, user_id))
        except (RedisError, OSError) as exc:
            self._warn("unclaim", exc)

    async def try_acquire(self, event_id: UUID) -> SlotResult:
        try:
            code = await self._acquire(keys=[self._key(event_id)])
        except (RedisError, OSError) as exc:
            self._warn("acquire", exc)
            return SlotResult.BYPASSED
        return _RESULT_BY_CODE.get(int(code), SlotResult.BYPASSED)

    async def release(self, event_id: UUID) -> None:
        try:
            await self._release(keys=[self._key(event_id)])
        except (RedisError, OSError) as exc:
            self._warn("release", exc)

    async def initialize(self, event_id: UUID, available: int) -> None:
        try:
            await self._client.set(
                self._key(event_id), max(0, available), ex=COUNTER_TTL_SECONDS, nx=True
            )
        except (RedisError, OSError) as exc:
            self._warn("initialize", exc)

    async def reconcile(self, event_id: UUID, available: int) -> None:
        try:
            await self._reconcile(keys=[self._key(event_id)], args=[max(0, available)])
        except (RedisError, OSError) as exc:
            self._warn("reconcile", exc)

    async def invalidate(self, event_id: UUID) -> None:
        try:
            await self._client.delete(self._key(event_id))
        except (RedisError, OSError) as exc:
            self._warn("invalidate", exc)

    @staticmethod
    def _warn(operation: str, exc: Exception) -> None:
        log.warning("redis_slots_unavailable", operation=operation, error=type(exc).__name__)
