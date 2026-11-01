import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = structlog.get_logger()

# INCR + EXPIRE atómicos: la ventana empieza con el primer fallo y no se renueva con los siguientes.
_RECORD = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


class RedisRateLimiter:
    """Contador de fallos por clave con ventana fija. Falla abierto si Redis no responde."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._record = client.register_script(_RECORD)

    @staticmethod
    def _key(key: str) -> str:
        return f"ratelimit:{key}"

    async def retry_after(self, key: str, limit: int) -> int:
        try:
            count = await self._client.get(self._key(key))
            if count is None or int(count) < limit:
                return 0
            ttl = await self._client.ttl(self._key(key))
        except (RedisError, OSError, ValueError) as exc:
            self._warn("retry_after", exc)
            return 0
        return max(int(ttl), 1)

    async def record_failure(self, key: str, window_seconds: int) -> None:
        try:
            await self._record(keys=[self._key(key)], args=[window_seconds])
        except (RedisError, OSError) as exc:
            self._warn("record_failure", exc)

    async def reset(self, key: str) -> None:
        try:
            await self._client.delete(self._key(key))
        except (RedisError, OSError) as exc:
            self._warn("reset", exc)

    @staticmethod
    def _warn(operation: str, exc: Exception) -> None:
        log.warning("redis_rate_limiter_unavailable", operation=operation, error=type(exc).__name__)
