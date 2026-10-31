from app.adapters.inbound.http.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.application.dto.commands import LoginCommand, RegisterUserCommand
from app.domain.models.user import User


def to_register_command(body: RegisterRequest) -> RegisterUserCommand:
    return RegisterUserCommand(email=body.email, password=body.password, full_name=body.full_name)


def to_login_command(body: LoginRequest) -> LoginCommand:
    return LoginCommand(email=body.email, password=body.password)


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
    )
