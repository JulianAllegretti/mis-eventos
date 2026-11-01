from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


def create_engine(database_url: str) -> AsyncEngine:
    # hide_parameters: los mensajes de error de SQLAlchemy no incluyen los valores de los
    # parámetros (correos, hashes), así no acaban en los logs si una sentencia falla.
    return create_async_engine(database_url, pool_pre_ping=True, hide_parameters=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
