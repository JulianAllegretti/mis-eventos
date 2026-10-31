"""Fixtures de integración: requieren PostgreSQL real.

Se activan con TEST_DATABASE_URL (y TEST_ADMIN_DATABASE_URL para crear la BD de pruebas).
Con docker compose: docker compose --profile test run --rm backend-test
"""

import os

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.adapters.outbound.persistence.database import create_engine, create_session_factory
from app.adapters.outbound.persistence.unit_of_work import SqlUnitOfWork


def _sync_dsn(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no está definida: se omiten las pruebas de integración")
    return url


@pytest.fixture(scope="session")
def migrated_database(database_url: str):
    """Crea la BD de pruebas si hace falta y aplica las migraciones (sincrónico a propósito:
    el env.py de Alembic usa asyncio.run)."""
    admin_url = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if admin_url:
        db_name = make_url(database_url).database
        with psycopg.connect(_sync_dsn(admin_url), autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if exists.fetchone() is None:
                conn.execute(f'CREATE DATABASE "{db_name}"')

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield database_url
    command.downgrade(config, "base")
    if previous is None:
        del os.environ["DATABASE_URL"]
    else:
        os.environ["DATABASE_URL"] = previous


@pytest.fixture
async def engine(migrated_database: str):
    engine = create_engine(migrated_database)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE events, speakers, users CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
def uow_factory(engine):
    session_factory = create_session_factory(engine)
    return lambda: SqlUnitOfWork(session_factory)
