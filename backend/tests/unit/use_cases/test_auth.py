from uuid import uuid4

import pytest

from app.application.dto.commands import LoginCommand, RegisterUserCommand
from app.application.use_cases.admin.ensure_admin_user import EnsureAdminUserUseCase
from app.application.use_cases.auth.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.errors import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    NotAuthenticated,
    ValidationFailed,
)
from app.domain.models.user import Role
from tests.fakes.in_memory import (
    FakePasswordHasher,
    FakeTokenService,
    FixedClock,
    make_uow_factory,
)


@pytest.fixture
def store():
    return {}


@pytest.fixture
def uow_factory(store):
    return make_uow_factory(store)


@pytest.fixture
def register(uow_factory):
    return RegisterUserUseCase(uow_factory, FakePasswordHasher(), FixedClock())


@pytest.fixture
def login(uow_factory):
    return LoginUserUseCase(uow_factory, FakePasswordHasher(), FakeTokenService())


@pytest.fixture
def current_user(uow_factory):
    return GetCurrentUserUseCase(uow_factory, FakeTokenService())


def _register_cmd(email="Ana@Example.com", password="secreto123", name="Ana"):
    return RegisterUserCommand(email=email, password=password, full_name=name)


class TestRegisterUser:
    async def test_creates_attendee_with_normalized_email_and_hashed_password(
        self, register, store
    ):
        user = await register.execute(_register_cmd())

        assert user.role is Role.ATTENDEE
        assert user.email == "ana@example.com"
        assert user.password_hash != "secreto123"
        assert store[user.id] is user

    async def test_rejects_duplicate_email_case_insensitively(self, register):
        await register.execute(_register_cmd(email="ana@example.com"))
        with pytest.raises(EmailAlreadyRegistered):
            await register.execute(_register_cmd(email="ANA@example.com"))

    async def test_rejects_short_password(self, register, store):
        with pytest.raises(ValidationFailed):
            await register.execute(_register_cmd(password="corta"))
        assert store == {}


class TestLoginUser:
    async def test_returns_token_for_valid_credentials(self, register, login):
        user = await register.execute(_register_cmd())

        result = await login.execute(LoginCommand(email="ANA@example.com", password="secreto123"))

        assert result.user.id == user.id
        assert result.token
        assert result.expires_in == 3600

    async def test_wrong_password_is_invalid_credentials(self, register, login):
        await register.execute(_register_cmd())
        with pytest.raises(InvalidCredentials):
            await login.execute(LoginCommand(email="ana@example.com", password="otra-clave"))

    async def test_unknown_email_gives_same_error(self, login):
        with pytest.raises(InvalidCredentials):
            await login.execute(LoginCommand(email="nadie@example.com", password="secreto123"))

    async def test_malformed_email_gives_same_error(self, login):
        with pytest.raises(InvalidCredentials):
            await login.execute(LoginCommand(email="no-es-correo", password="secreto123"))

    async def test_inactive_user_cannot_login(self, register, login, store):
        user = await register.execute(_register_cmd())
        store[user.id].is_active = False
        with pytest.raises(InvalidCredentials):
            await login.execute(LoginCommand(email="ana@example.com", password="secreto123"))


class TestGetCurrentUser:
    async def test_resolves_user_from_valid_token(self, register, login, current_user):
        await register.execute(_register_cmd())
        result = await login.execute(LoginCommand(email="ana@example.com", password="secreto123"))

        assert (await current_user.execute(result.token)).id == result.user.id

    @pytest.mark.parametrize("token", [None, "", "basura", "token:no-es-uuid:attendee"])
    async def test_rejects_missing_or_invalid_token(self, current_user, token):
        with pytest.raises(NotAuthenticated):
            await current_user.execute(token)

    async def test_rejects_token_of_deleted_user(self, current_user):
        with pytest.raises(NotAuthenticated):
            await current_user.execute(f"token:{uuid4()}:attendee")

    async def test_rejects_deactivated_user(self, register, login, current_user, store):
        await register.execute(_register_cmd())
        result = await login.execute(LoginCommand(email="ana@example.com", password="secreto123"))
        store[result.user.id].is_active = False
        with pytest.raises(NotAuthenticated):
            await current_user.execute(result.token)

    async def test_reads_role_from_database_not_from_token(
        self, register, login, current_user, store
    ):
        await register.execute(_register_cmd())
        result = await login.execute(LoginCommand(email="ana@example.com", password="secreto123"))
        store[result.user.id].role = Role.ADMIN

        assert (await current_user.execute(result.token)).role is Role.ADMIN


class TestEnsureAdminUser:
    async def test_creates_admin_once(self, uow_factory, store):
        use_case = EnsureAdminUserUseCase(uow_factory, FakePasswordHasher(), FixedClock())

        assert await use_case.execute("Admin@Example.com", "clave-segura-1") is True
        assert await use_case.execute("admin@example.com", "clave-segura-1") is False

        (admin,) = store.values()
        assert admin.role is Role.ADMIN
        assert admin.email == "admin@example.com"
