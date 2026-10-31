from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    # Timeouts cortos: si Redis cae, la API debe degradarse rápido y no quedarse esperando.
    return Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5
    )


class RedisHealthProbe:
    name = "redis"
    critical = False  # sin Redis la API sigue funcionando (ADR 0005)

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def check(self) -> bool:
        return bool(await self._client.ping())
