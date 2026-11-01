from fastapi import APIRouter, Depends, Request, Response, status

from app.adapters.inbound.http.config import HttpConfig
from app.adapters.inbound.http.cookies import clear_session_cookie, set_session_cookie
from app.adapters.inbound.http.dependencies import (
    AppContainer,
    current_user,
    get_container,
    get_http_config,
)
from app.adapters.inbound.http.mappers.auth import (
    to_login_command,
    to_register_command,
    to_user_response,
)
from app.adapters.inbound.http.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.adapters.inbound.http.schemas.errors import ErrorResponse
from app.domain.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Registra un usuario con rol attendee",
)
async def register(
    body: RegisterRequest, container: AppContainer = Depends(get_container)
) -> UserResponse:
    user = await container.register_user.execute(to_register_command(body))
    return to_user_response(user)


@router.post(
    "/login",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Inicia sesión: fija la cookie HttpOnly y no devuelve el token",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    container: AppContainer = Depends(get_container),
    config: HttpConfig = Depends(get_http_config),
) -> UserResponse:
    client_ip = request.client.host if request.client else None
    result = await container.login_user.execute(to_login_command(body, client_ip))
    set_session_cookie(response, result.token, result.expires_in, config.cookie_secure)
    return to_user_response(result.user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
    summary="Cierra la sesión borrando la cookie",
)
async def logout(
    _: User = Depends(current_user), config: HttpConfig = Depends(get_http_config)
) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, config.cookie_secure)
    return response


@router.get(
    "/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Usuario de la sesión actual",
)
async def me(user: User = Depends(current_user)) -> UserResponse:
    return to_user_response(user)
