from pydantic import BaseModel

from app.adapters.inbound.http.schemas.auth import UserResponse
from app.domain.models.user import Role


class UserAdminUpdateRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserPage(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
