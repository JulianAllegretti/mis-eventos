import asyncio
from uuid import uuid4

from app.adapters.outbound.cache.redis_client import create_redis
from app.adapters.outbound.cache.redis_rate_limiter import RedisRateLimiter
from app.adapters.outbound.security.argon2_hasher import Argon2PasswordHasher
from app.adapters.outbound.security.jwt_token_service import JwtTokenService
from app.adapters.outbound.system.system_clock import SystemClock
from app.application.dto.commands import LoginCommand, RegisterUserCommand
from app.application.dto.policies import LoginRateLimit
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.errors import InvalidCredentials, TooManyAttempts
from tests.fakes.in_memory import FakeMetrics


class TestRedisRateLimiter:
    async def test_is_open_until_the_limit_is_reached(self, redis_client):
        limiter, key = RedisRateLimiter(redis_client), f"k-{uuid4()}"

        for _ in range(2):
            await limiter.record_failure(key, 60)
        assert await limiter.retry_after(key, 3) == 0

        await limiter.record_failure(key, 60)
        assert 0 < await limiter.retry_after(key, 3) <= 60

    async def test_the_window_starts_at_the_first_failure_and_is_not_extended(self, redis_client):
        limiter, key = RedisRateLimiter(redis_client), f"k-{uuid4()}"
        await limiter.record_failure(key, 100)
        ttl_first = await redis_client.ttl(f"ratelimit:{key}")

        for _ in range(4):
            await limiter.record_failure(key, 100)

        assert await redis_client.ttl(f"ratelimit:{key}") <= ttl_first  # no se renueva

    async def test_the_block_lifts_when_the_window_expires(self, redis_client):
        limiter, key = RedisRateLimiter(redis_client), f"k-{uuid4()}"
        await limiter.record_failure(key, 1)
        assert await limiter.retry_after(key, 1) >= 1

        await asyncio.sleep(1.3)

        assert await limiter.retry_after(key, 1) == 0

    async def test_reset_clears_the_failures(self, redis_client):
        limiter, key = RedisRateLimiter(redis_client), f"k-{uuid4()}"
        for _ in range(3):
            await limiter.record_failure(key, 60)
        await limiter.reset(key)
        assert await limiter.retry_after(key, 3) == 0

    async def test_keys_are_independent(self, redis_client):
        limiter = RedisRateLimiter(redis_client)
        a, b = f"a-{uuid4()}", f"b-{uuid4()}"
        for _ in range(3):
            await limiter.record_failure(a, 60)

        assert await limiter.retry_after(a, 3) > 0
        assert await limiter.retry_after(b, 3) == 0

    async def test_concurrent_failures_are_all_counted(self, redis_client):
        limiter, key = RedisRateLimiter(redis_client), f"k-{uuid4()}"

        await asyncio.gather(*(limiter.record_failure(key, 60) for _ in range(100)))

        assert int(await redis_client.get(f"ratelimit:{key}")) == 100
        assert await redis_client.ttl(f"ratelimit:{key}") > 0  # y la clave siempre expira

    async def test_unreachable_redis_never_blocks_anyone(self):
        dead = RedisRateLimiter(create_redis("redis://127.0.0.1:1/0"))

        assert await dead.retry_after("k", 1) == 0
        await dead.record_failure("k", 60)  # no lanza
        await dead.reset("k")  # no lanza


class TestLoginWithRealRedisAndDatabase:
    async def test_a_brute_force_attempt_is_stopped_and_the_real_user_gets_back_in_after_reset(
        self, uow_factory, redis_client
    ):
        clock = SystemClock()
        hasher = Argon2PasswordHasher()
        limiter = RedisRateLimiter(redis_client)
        await RegisterUserUseCase(uow_factory, hasher, clock).execute(
            RegisterUserCommand("ana@example.com", "secreto123", "Ana")
        )
        login = LoginUserUseCase(
            uow_factory,
            hasher,
            JwtTokenService("s" * 32, 60, clock),
            limiter,
            LoginRateLimit(max_failures_per_email=3, max_failures_per_ip=100, window_seconds=60),
            FakeMetrics(),
        )

        for _ in range(3):
            try:
                await login.execute(LoginCommand("ana@example.com", "mala", "203.0.113.5"))
            except InvalidCredentials:
                pass
        try:
            await login.execute(LoginCommand("ana@example.com", "secreto123", "203.0.113.5"))
        except TooManyAttempts as exc:
            assert 0 < exc.retry_after <= 60
        else:
            raise AssertionError("debió bloquearse tras 3 fallos")

        # Quien conoce la contraseña, desde otra cuenta de correo no afectada, sigue entrando.
        await RegisterUserUseCase(uow_factory, hasher, clock).execute(
            RegisterUserCommand("luis@example.com", "secreto123", "Luis")
        )
        assert (
            await login.execute(LoginCommand("luis@example.com", "secreto123", "203.0.113.5"))
        ).token

        await limiter.reset(
            "login:email:ana@example.com"
        )  # lo que hace un acierto o el vencimiento
        assert (
            await login.execute(LoginCommand("ana@example.com", "secreto123", "203.0.113.5"))
        ).token
