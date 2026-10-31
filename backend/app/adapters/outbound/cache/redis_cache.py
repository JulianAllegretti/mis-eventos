import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.outbound.cache import CacheLookup

log = structlog.get_logger()


class RedisCache:
    """Caché de lectura con invalidación por grupo en O(1).

    Cada grupo tiene un número de versión; las claves lo incluyen. Invalidar es incrementar la
    versión: las claves viejas dejan de leerse y expiran solas por TTL. La versión devuelta por
    `get` evita publicar un valor calculado con datos anteriores a una invalidación.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    @staticmethod
    def _version_key(group: str) -> str:
        return f"cache:{group}:version"

    @staticmethod
    def _value_key(group: str, version: str, key: str) -> str:
        return f"cache:{group}:{version}:{key}"

    async def get(self, group: str, key: str) -> CacheLookup:
        try:
            version = str(await self._client.get(self._version_key(group)) or "0")
            raw = await self._client.get(self._value_key(group, version, key))
        except (RedisError, OSError) as exc:
            self._warn("get", exc)
            return CacheLookup(value=None, version="0")
        return CacheLookup(value=str(raw) if raw is not None else None, version=version)

    async def set(self, group: str, key: str, version: str, value: str, ttl_seconds: int) -> None:
        try:
            await self._client.set(self._value_key(group, version, key), value, ex=ttl_seconds)
        except (RedisError, OSError) as exc:
            self._warn("set", exc)

    async def invalidate_group(self, group: str) -> None:
        try:
            await self._client.incr(self._version_key(group))
        except (RedisError, OSError) as exc:
            self._warn("invalidate", exc)

    @staticmethod
    def _warn(operation: str, exc: Exception) -> None:
        log.warning("redis_cache_unavailable", operation=operation, error=type(exc).__name__)
