from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.adapters.inbound.http.dependencies import (
    AppContainer,
    current_user,
    get_container,
    optional_user,
)
from app.adapters.inbound.http.mappers.sessions import (
    to_create_session_command,
    to_session_registration_response,
    to_session_response,
    to_update_session_command,
)
from app.adapters.inbound.http.schemas.errors import error_responses
from app.adapters.inbound.http.schemas.sessions import (
    SessionCreateRequest,
    SessionRegistrationResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.application.dto.commands import SessionActionCommand
from app.application.dto.queries import ListEventSessionsQuery
from app.domain.models.user import User

router = APIRouter(tags=["sessions"])

_ERRORS = error_responses(401, 403, 404, 409, 422)


@router.get(
    "/events/{event_id}/sessions",
    response_model=list[SessionResponse],
    responses=_ERRORS,
    summary="Agenda del evento, ordenada por inicio",
)
async def list_event_sessions(
    event_id: UUID,
    viewer: User | None = Depends(optional_user),
    container: AppContainer = Depends(get_container),
) -> list[SessionResponse]:
    views = await container.list_event_sessions.execute(
        ListEventSessionsQuery(viewer=viewer, event_id=event_id)
    )
    return [to_session_response(v) for v in views]


@router.post(
    "/events/{event_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Crea una sesión con ponente (dueño del evento o admin)",
)
async def create_session(
    event_id: UUID,
    body: SessionCreateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SessionResponse:
    view = await container.create_session.execute(to_create_session_command(event_id, body, actor))
    return to_session_response(view)


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses=_ERRORS,
    summary="Edita una sesión (dueño del evento o admin)",
)
async def update_session(
    session_id: UUID,
    body: SessionUpdateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SessionResponse:
    view = await container.update_session.execute(
        to_update_session_command(session_id, body, actor)
    )
    return to_session_response(view)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Borra una sesión sin inscritos",
)
async def delete_session(
    session_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.delete_session.execute(SessionActionCommand(actor=actor, session_id=session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sessions/{session_id}/registrations",
    response_model=SessionRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Inscribirse a una sesión (exige estar inscrito al evento, cupo y sin solapes)",
)
async def register_to_session(
    session_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SessionRegistrationResponse:
    registration = await container.register_to_session.execute(
        SessionActionCommand(actor=actor, session_id=session_id)
    )
    return to_session_registration_response(registration)


@router.delete(
    "/sessions/{session_id}/registrations/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Cancela tu inscripción a la sesión",
)
async def cancel_session_registration(
    session_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.cancel_session_registration.execute(
        SessionActionCommand(actor=actor, session_id=session_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
