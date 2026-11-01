import pytest

from app.application.dto.commands import LoginCommand, RegisterUserCommand
from app.application.dto.policies import LoginRateLimit
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.errors import InvalidCredentials, TooManyAttempts
from tests.fakes.in_memory import (
    FakeMetrics,
    FakePasswordHasher,
    FakeRateLimiter,
    FakeTokenService,
    FixedClock,
    make_uow_factory,
)

POLICY = LoginRateLimit(max_failures_per_email=3, max_failures_per_ip=5, window_seconds=900)


@pytest.fixture
def limiter():
    return FakeRateLimiter()


@pytest.fixture
def metrics():
    return FakeMetrics()


@pytest.fixture
async def login(limiter, metrics):
    uow_factory = make_uow_factory({})
    await RegisterUserUseCase(uow_factory, FakePasswordHasher(), FixedClock()).execute(
        RegisterUserCommand("ana@example.com", "secreto123", "Ana")
    )
    return LoginUserUseCase(
        uow_factory, FakePasswordHasher(), FakeTokenService(), limiter, POLICY, metrics
    )


def _cmd(password="secreto123", email="ana@example.com", ip="10.0.0.1"):
    return LoginCommand(email=email, password=password, client_ip=ip)


async def _fail(login, times, **kw):
    for _ in range(times):
        with pytest.raises(InvalidCredentials):
            await login.execute(_cmd("incorrecta", **kw))


class TestPerEmail:
    async def test_blocks_after_the_allowed_failures_even_with_the_right_password(self, login):
        await _fail(login, 3)

        with pytest.raises(TooManyAttempts) as exc:
            await login.execute(_cmd())  # contraseña correcta, pero la cuenta está bloqueada

        assert exc.value.retry_after == 60
        assert "1 minuto" in exc.value.message

    async def test_the_limit_follows_the_email_across_different_ips(self, login):
        await _fail(login, 3, ip="10.0.0.1")

        with pytest.raises(TooManyAttempts):
            await login.execute(_cmd(ip="10.0.0.99"))

    async def test_unknown_emails_are_limited_too(self, login):
        """Si solo se limitaran las cuentas reales, el bloqueo revelaría cuáles existen."""
        await _fail(login, 3, email="fantasma@example.com")

        with pytest.raises(TooManyAttempts):
            await login.execute(_cmd("x", email="fantasma@example.com"))

    async def test_email_is_normalized_so_case_tricks_do_not_evade_the_limit(self, login):
        await _fail(login, 3, email="ANA@Example.com")
        with pytest.raises(TooManyAttempts):
            await login.execute(_cmd(email="ana@example.com"))

    async def test_a_success_clears_the_accounts_failures(self, login):
        await _fail(login, 2)
        await login.execute(_cmd())  # entra y reinicia el contador

        await _fail(login, 2)  # vuelve a tener margen
        assert (await login.execute(_cmd())).token

    async def test_blocked_attempts_do_not_extend_the_block(self, login, limiter):
        await _fail(login, 3)
        for _ in range(5):
            with pytest.raises(TooManyAttempts):
                await login.execute(_cmd())

        assert limiter.failures["login:email:ana@example.com"] == 3


class TestPerIp:
    async def test_one_origin_spraying_many_accounts_gets_blocked(self, login):
        for i in range(5):
            with pytest.raises(InvalidCredentials):
                await login.execute(_cmd("x", email=f"victima{i}@example.com", ip="203.0.113.7"))

        with pytest.raises(TooManyAttempts):
            await login.execute(_cmd("x", email="otra@example.com", ip="203.0.113.7"))

    async def test_other_origins_are_not_affected(self, login):
        for i in range(5):
            with pytest.raises(InvalidCredentials):
                await login.execute(_cmd("x", email=f"victima{i}@example.com", ip="203.0.113.7"))

        assert (await login.execute(_cmd(ip="198.51.100.2"))).token

    async def test_without_a_known_ip_only_the_email_limit_applies(self, login, limiter):
        await _fail(login, 2, ip=None)
        assert not any(key.startswith("login:ip:") for key in limiter.failures)


class TestMetricsAndMessages:
    async def test_every_outcome_is_counted(self, login, metrics):
        await login.execute(_cmd())
        await _fail(login, 3)
        with pytest.raises(TooManyAttempts):
            await login.execute(_cmd())

        assert metrics.count("login_attempt", "success") == 1
        assert metrics.count("login_attempt", "invalid") == 3
        assert metrics.count("login_attempt", "rate_limited") == 1

    @pytest.mark.parametrize(
        ("seconds", "text"), [(30, "1 minuto"), (61, "2 minutos"), (900, "15 minutos")]
    )
    def test_wait_time_is_rounded_up_to_whole_minutes(self, seconds, text):
        assert text in TooManyAttempts(seconds).message

    def test_error_does_not_reveal_whether_the_account_exists(self):
        assert "cuenta" not in TooManyAttempts(60).message.lower()
