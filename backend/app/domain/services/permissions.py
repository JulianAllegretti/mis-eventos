from app.domain.errors import Forbidden
from app.domain.models.event import Event, EventStatus
from app.domain.models.user import Role, User

MANAGERS = (Role.ORGANIZER, Role.ADMIN)


def ensure_role(user: User, *roles: Role) -> None:
    if user.role not in roles:
        raise Forbidden()


def ensure_can_manage_event(user: User, event: Event) -> None:
    """Administrar un evento: su organizador (con rol vigente) o un admin."""
    ensure_role(user, *MANAGERS)
    if user.role is not Role.ADMIN and event.organizer_id != user.id:
        raise Forbidden()


def can_view_event(viewer: User | None, event: Event) -> bool:
    """Los borradores solo los ven su organizador y los admin."""
    if event.status is not EventStatus.DRAFT:
        return True
    return viewer is not None and (viewer.role is Role.ADMIN or event.organizer_id == viewer.id)
