"""Los adaptadores de seguridad son código propio sin I/O externo: se prueban sin Docker."""

from datetime import timedelta

import jwt

from app.adapters.outbound.security.argon2_hasher import Argon2PasswordHasher
from app.adapters.outbound.security.jwt_token_service import ALGORITHM, JwtTokenService
from app.domain.models.user import Role, User
from tests.fakes.in_memory import FIXED_NOW, FixedClock

SECRET = "s" * 32


def _user() -> User:
    return User.new(
        email="ana@example.com",
        password_hash="h",
        full_name="Ana",
        now=FIXED_NOW,
        role=Role.ORGANIZER,
    )


async def test_argon2_hash_verifies_and_is_not_plaintext():
    hasher = Argon2PasswordHasher()
    hashed = await hasher.hash("secreto123")

    assert hashed.startswith("$argon2id$")
    assert "secreto123" not in hashed
    assert await hasher.verify("secreto123", hashed) is True
    assert await hasher.verify("incorrecta", hashed) is False


async def test_argon2_uses_a_different_salt_each_time():
    hasher = Argon2PasswordHasher()
    assert await hasher.hash("secreto123") != await hasher.hash("secreto123")


async def test_argon2_verify_returns_false_for_garbage_hash():
    assert await Argon2PasswordHasher().verify("secreto123", "no-es-un-hash") is False


def test_jwt_round_trip_carries_user_and_role():
    service = JwtTokenService(SECRET, 60, FixedClock())
    user = _user()

    claims = service.decode(service.issue(user))

    assert claims is not None
    assert claims.user_id == user.id
    assert claims.role is Role.ORGANIZER
    assert service.ttl_seconds == 3600


def test_jwt_rejects_wrong_secret_garbage_and_expired_tokens():
    user = _user()
    issuer = JwtTokenService(SECRET, 60, FixedClock())

    assert (
        JwtTokenService("otro-secreto-" + "x" * 20, 60, FixedClock()).decode(issuer.issue(user))
        is None
    )
    assert issuer.decode("basura") is None

    long_ago = FixedClock(FIXED_NOW - timedelta(days=2))
    assert issuer.decode(JwtTokenService(SECRET, 60, long_ago).issue(user)) is None


def test_jwt_rejects_tokens_signed_with_none_algorithm():
    forged = jwt.encode({"sub": str(_user().id), "exp": 9999999999}, key="", algorithm="none")
    assert JwtTokenService(SECRET, 60, FixedClock()).decode(forged) is None
    assert ALGORITHM == "HS256"


async def test_concurrent_hashes_are_capped_so_a_burst_cannot_exhaust_memory():
    import asyncio
    import time
    from types import SimpleNamespace

    hasher = Argon2PasswordHasher(max_concurrency=2)
    running = peak = 0

    def slow_hash(password: str) -> str:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        time.sleep(0.05)
        running -= 1
        return f"hash:{password}"

    hasher._hasher = SimpleNamespace(hash=slow_hash)  # type: ignore[assignment]

    results = await asyncio.gather(*(hasher.hash(f"p{i}") for i in range(10)))

    assert results == [f"hash:p{i}" for i in range(10)]  # todos terminan, en cola
    assert peak == 2  # nunca más de 2 a la vez


async def test_verify_shares_the_same_cap():
    import asyncio
    import time
    from types import SimpleNamespace

    hasher = Argon2PasswordHasher(max_concurrency=1)
    running = peak = 0

    def slow_verify(_hash: str, _password: str) -> bool:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        time.sleep(0.03)
        running -= 1
        return True

    hasher._hasher = SimpleNamespace(verify=slow_verify)  # type: ignore[assignment]

    await asyncio.gather(*(hasher.verify("x", "h") for _ in range(6)))

    assert peak == 1
