from typing import Protocol

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from app.adapters.inbound.http.config import HttpConfig
from app.adapters.inbound.http.cookies import SESSION_COOKIE_NAME
from app.application.ports.inbound.admin import EnsureAdminUser, ListUsers, UpdateUser
from app.application.ports.inbound.auth import GetCurrentUser, LoginUser, RegisterUser
from app.application.ports.inbound.events import (
    CancelEvent,
    CreateEvent,
    DeleteEvent,
    FinishEvent,
    GetEvent,
    PublishEvent,
    SearchEvents,
    UpdateEvent,
)
from app.application.ports.inbound.health import CheckReadiness
from app.application.ports.inbound.speakers import (
    CreateSpeaker,
    DeleteSpeaker,
    GetSpeaker,
    ListSpeakers,
    UpdateSpeaker,
)
from app.domain.errors import NotAuthenticated
from app.domain.models.user import User


class AppContainer(Protocol):
    """Casos de uso que el adaptador HTTP necesita. El Container del bootstrap lo cumple."""

    register_user: RegisterUser
    login_user: LoginUser
    get_current_user: GetCurrentUser
    ensure_admin: EnsureAdminUser
    check_readiness: CheckReadiness
    create_event: CreateEvent
    update_event: UpdateEvent
    get_event: GetEvent
    search_events: SearchEvents
    delete_event: DeleteEvent
    publish_event: PublishEvent
    finish_event: FinishEvent
    cancel_event: CancelEvent
    create_speaker: CreateSpeaker
    update_speaker: UpdateSpeaker
    delete_speaker: DeleteSpeaker
    get_speaker: GetSpeaker
    list_speakers: ListSpeakers
    list_users: ListUsers
    update_user: UpdateUser


# Declara el esquema de seguridad (cookie) en OpenAPI/Swagger.
session_cookie = APIKeyCookie(name=SESSION_COOKIE_NAME, auto_error=False)


def get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


def get_http_config(request: Request) -> HttpConfig:
    config: HttpConfig = request.app.state.http_config
    return config


async def current_user(
    request: Request,
    token: str | None = Depends(session_cookie),
    container: AppContainer = Depends(get_container),
) -> User:
    user = await container.get_current_user.execute(token)
    request.state.user_id = str(user.id)
    return user


async def optional_user(
    request: Request,
    token: str | None = Depends(session_cookie),
    container: AppContainer = Depends(get_container),
) -> User | None:
    """Para rutas públicas que muestran más a quien tiene sesión. Un token inválido = anónimo."""
    try:
        user = await container.get_current_user.execute(token)
    except NotAuthenticated:
        return None
    request.state.user_id = str(user.id)
    return user
