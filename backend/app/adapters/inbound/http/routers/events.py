from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.adapters.inbound.http.dependencies import (
    AppContainer,
    current_user,
    get_container,
    optional_user,
)
from app.adapters.inbound.http.mappers.events import (
    to_create_event_command,
    to_event_page,
    to_event_response,
    to_update_event_command,
)
from app.adapters.inbound.http.schemas.errors import error_responses
from app.adapters.inbound.http.schemas.events import (
    EventCreateRequest,
    EventPage,
    EventResponse,
    EventUpdateRequest,
)
from app.application.dto.commands import EventActionCommand
from app.application.dto.queries import GetEventQuery, SearchEventsQuery
from app.domain.models.event import EventStatus
from app.domain.models.user import User

router = APIRouter(prefix="/events", tags=["events"])

_ERRORS = error_responses(401, 403, 404, 409, 422)


@router.get("", response_model=EventPage, summary="Lista y busca eventos (paginado)")
async def search_events(
    q: Annotated[str | None, Query(max_length=100, description="Parte del nombre")] = None,
    status_filter: Annotated[EventStatus | None, Query(alias="status")] = None,
    scope: Annotated[
        Literal["all", "mine"], Query(description="mine incluye tus borradores")
    ] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    viewer: User | None = Depends(optional_user),
    container: AppContainer = Depends(get_container),
) -> EventPage:
    result = await container.search_events.execute(
        SearchEventsQuery(
            viewer=viewer,
            q=q,
            status=status_filter,
            mine=scope == "mine",
            page=page,
            page_size=page_size,
        )
    )
    return to_event_page(result)


@router.get("/{event_id}", response_model=EventResponse, responses=_ERRORS, summary="Detalle")
async def get_event(
    event_id: UUID,
    viewer: User | None = Depends(optional_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.get_event.execute(GetEventQuery(viewer=viewer, event_id=event_id))
    return to_event_response(event)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Crea un evento en borrador (organizer o admin)",
)
async def create_event(
    body: EventCreateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.create_event.execute(to_create_event_command(body, actor))
    return to_event_response(event)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    responses=_ERRORS,
    summary="Edita datos del evento (dueño o admin)",
)
async def update_event(
    event_id: UUID,
    body: EventUpdateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.update_event.execute(to_update_event_command(event_id, body, actor))
    return to_event_response(event)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Borra un evento sin inscripciones (dueño o admin)",
)
async def delete_event(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.delete_event.execute(EventActionCommand(actor=actor, event_id=event_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{event_id}/publish",
    response_model=EventResponse,
    responses=_ERRORS,
    summary="draft → published",
)
async def publish_event(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.publish_event.execute(EventActionCommand(actor, event_id))
    return to_event_response(event)


@router.post(
    "/{event_id}/finish",
    response_model=EventResponse,
    responses=_ERRORS,
    summary="published → finished (cierre manual)",
)
async def finish_event(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.finish_event.execute(EventActionCommand(actor, event_id))
    return to_event_response(event)


@router.post(
    "/{event_id}/cancel",
    response_model=EventResponse,
    responses=_ERRORS,
    summary="draft|published → cancelled",
)
async def cancel_event(
    event_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> EventResponse:
    event = await container.cancel_event.execute(EventActionCommand(actor, event_id))
    return to_event_response(event)
