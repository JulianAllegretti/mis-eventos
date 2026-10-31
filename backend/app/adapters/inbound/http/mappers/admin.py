from uuid import UUID

from app.adapters.inbound.http.mappers.auth import to_user_response
from app.adapters.inbound.http.schemas.admin import UserAdminUpdateRequest, UserPage
from app.application.dto.commands import UpdateUserCommand
from app.application.dto.read_models import Page
from app.domain.models.user import User


def to_update_user_command(
    user_id: UUID, body: UserAdminUpdateRequest, actor: User
) -> UpdateUserCommand:
    return UpdateUserCommand(
        actor=actor, user_id=user_id, changes=body.model_dump(exclude_unset=True)
    )


def to_user_page(page: Page[User]) -> UserPage:
    return UserPage(
        items=[to_user_response(u) for u in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
