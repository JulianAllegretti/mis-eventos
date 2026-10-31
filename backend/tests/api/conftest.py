from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.bootstrap.app import create_app
from app.bootstrap.settings import Settings
from app.domain.models.user import Role, User
from tests.factories import make_user
from tests.fakes.container import build_fake_container
from tests.fakes.in_memory import FIXED_NOW, FakeTokenService

ALLOWED_ORIGIN = "http://localhost:5173"


def when(days: float = 0, hours: float = 0) -> str:
    """Instante ISO-8601 con zona horaria, relativo al reloj fijo de los tests."""
    instant: datetime = FIXED_NOW + timedelta(days=days, hours=hours)
    return instant.isoformat()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://unused",
        jwt_secret="x" * 32,
        cookie_secure=False,  # TestClient usa http://testserver
        allowed_origins=[ALLOWED_ORIGIN],
    )


@pytest.fixture
def users() -> dict:
    return {}


@pytest.fixture
def events() -> dict:
    return {}


@pytest.fixture
def speakers() -> dict:
    return {}


@pytest.fixture
def make_client(settings, users, events, speakers):
    def _make(**container_kwargs) -> TestClient:
        container = build_fake_container(users, events, speakers, **container_kwargs)
        return TestClient(create_app(settings, container))

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def as_user(client, users):
    """Crea un usuario con el rol dado e inicia sesión como él en `client`."""

    def _login(role: Role = Role.ATTENDEE) -> User:
        user = make_user(role)
        users[user.id] = user
        client.cookies.set("access_token", FakeTokenService().issue(user))
        client.headers["Origin"] = ALLOWED_ORIGIN
        return user

    return _login
