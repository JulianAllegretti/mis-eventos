from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.adapters.inbound.http.dependencies import AppContainer, current_user, get_container
from app.adapters.inbound.http.mappers.admin import to_update_user_command, to_user_page
from app.adapters.inbound.http.mappers.auth import to_user_response
from app.adapters.inbound.http.schemas.admin import UserAdminUpdateRequest, UserPage
from app.adapters.inbound.http.schemas.auth import UserResponse
from app.adapters.inbound.http.schemas.errors import error_responses
from app.application.dto.queries import ListUsersQuery
from app.domain.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

_ERRORS = error_responses(401, 403, 404, 422)


@router.get("/users", response_model=UserPage, responses=_ERRORS, summary="Lista usuarios (admin)")
async def list_users(
    q: Annotated[str | None, Query(max_length=100, description="Correo o nombre")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> UserPage:
    result = await container.list_users.execute(
        ListUsersQuery(actor=actor, q=q, page=page, page_size=page_size)
    )
    return to_user_page(result)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    responses=_ERRORS,
    summary="Cambia el rol o activa/desactiva a un usuario (admin)",
)
async def update_user(
    user_id: UUID,
    body: UserAdminUpdateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> UserResponse:
    user = await container.update_user.execute(to_update_user_command(user_id, body, actor))
    return to_user_response(user)
