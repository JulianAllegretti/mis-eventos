from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.adapters.inbound.http.dependencies import AppContainer, current_user, get_container
from app.adapters.inbound.http.mappers.sessions import (
    to_attendee_page,
    to_my_registration_response,
    to_registration_response,
)
from app.adapters.inbound.http.schemas.errors import error_responses
from app.adapters.inbound.http.schemas.sessions import (
    AttendeePage,
    MyRegistrationResponse,
    RegistrationResponse,
)
from app.application.dto.commands import EventActionCommand
from app.application.dto.queries import ListAttendeesQuery, ListMyRegistrationsQuery
from app.domain.models.user import User

router = APIRouter(tags=["registrations"])

_ERRORS = error_responses(401, 403, 404, 409, 422)


@router.post(
    "/events/{event_id}/registrations",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Inscribirse a un evento publicado (409 si está lleno o ya estás inscrito)",
)
async def register_to_event(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> RegistrationResponse:
    registration = await container.register_to_event.execute(
        EventActionCommand(actor=actor, event_id=event_id)
    )
    return to_registration_response(registration)


@router.delete(
    "/events/{event_id}/registrations/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Cancela tu inscripción (también tus inscripciones a sus sesiones)",
)
async def cancel_event_registration(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.cancel_event_registration.execute(
        EventActionCommand(actor=actor, event_id=event_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/events/{event_id}/registrations",
    response_model=AttendeePage,
    responses=_ERRORS,
    summary="Asistentes del evento (dueño o admin)",
)
async def list_event_attendees(
    event_id: UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> AttendeePage:
    result = await container.list_event_attendees.execute(
        ListAttendeesQuery(actor=actor, event_id=event_id, page=page, page_size=page_size)
    )
    return to_attendee_page(result)


@router.get(
    "/users/me/registrations",
    response_model=list[MyRegistrationResponse],
    responses=_ERRORS,
    summary="Eventos en los que estoy inscrito, con mis sesiones",
)
async def list_my_registrations(
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> list[MyRegistrationResponse]:
    items = await container.list_my_registrations.execute(ListMyRegistrationsQuery(user=actor))
    return [to_my_registration_response(i) for i in items]
