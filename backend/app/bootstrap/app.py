from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.adapters.inbound.http.app_factory import build_http_app
from app.adapters.inbound.http.config import HttpConfig
from app.adapters.outbound.observability.logging import configure_logging
from app.bootstrap.container import Container, build_container
from app.bootstrap.settings import Settings

log = structlog.get_logger()


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Crea la aplicación. Si no se entrega un contenedor (producción), se construye al arrancar;
    los tests entregan uno con fakes y no tocan PostgreSQL ni Redis."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        active = container if container is not None else build_container(settings)
        app.state.container = active
        if owned and settings.admin_email and settings.admin_password:
            created = await active.ensure_admin.execute(
                settings.admin_email, settings.admin_password
            )
            log.info("admin_seed", created=created)
        try:
            yield
        finally:
            if owned:
                await active.aclose()

    config = HttpConfig(
        cookie_secure=settings.cookie_secure,
        allowed_origins=tuple(settings.allowed_origins),
    )
    app = build_http_app(config, lifespan=lifespan)
    if container is not None:
        app.state.container = container  # disponible aunque no se ejecute el lifespan
    return app
