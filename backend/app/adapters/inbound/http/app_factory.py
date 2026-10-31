from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.http.config import HttpConfig
from app.adapters.inbound.http.error_handlers import register_error_handlers
from app.adapters.inbound.http.middleware.origin_check import OriginCheckMiddleware
from app.adapters.inbound.http.middleware.request_context import RequestContextMiddleware
from app.adapters.inbound.http.routers import admin, auth, events, health, speakers

API_PREFIX = "/api/v1"


def build_http_app(
    config: HttpConfig,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
    **state: Any,
) -> FastAPI:
    """Monta la aplicación FastAPI. El contenedor se asigna a app.state.container."""
    app = FastAPI(
        title="Mis Eventos API",
        version="0.1.0",
        description="Gestión de eventos, sesiones, ponentes e inscripciones.",
        lifespan=lifespan,
    )
    app.state.http_config = config
    for key, value in state.items():
        setattr(app.state, key, value)

    register_error_handlers(app)

    # Starlette aplica los middlewares de último a primero: CORS queda más externo.
    app.add_middleware(OriginCheckMiddleware, allowed_origins=config.allowed_origins)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(events.router, prefix=API_PREFIX)
    app.include_router(speakers.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    return app
