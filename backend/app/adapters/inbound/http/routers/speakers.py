from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.adapters.inbound.http.dependencies import AppContainer, current_user, get_container
from app.adapters.inbound.http.mappers.speakers import (
    to_create_speaker_command,
    to_speaker_page,
    to_speaker_response,
    to_update_speaker_command,
)
from app.adapters.inbound.http.schemas.errors import error_responses
from app.adapters.inbound.http.schemas.speakers import (
    SpeakerCreateRequest,
    SpeakerPage,
    SpeakerResponse,
    SpeakerUpdateRequest,
)
from app.application.dto.commands import SpeakerActionCommand
from app.application.dto.queries import GetSpeakerQuery, ListSpeakersQuery
from app.domain.models.user import User

router = APIRouter(prefix="/speakers", tags=["speakers"])

_ERRORS = error_responses(401, 403, 404, 422)


@router.get("", response_model=SpeakerPage, responses=_ERRORS, summary="Lista ponentes")
async def list_speakers(
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SpeakerPage:
    result = await container.list_speakers.execute(
        ListSpeakersQuery(actor=actor, q=q, page=page, page_size=page_size)
    )
    return to_speaker_page(result)


@router.get("/{speaker_id}", response_model=SpeakerResponse, responses=_ERRORS)
async def get_speaker(
    speaker_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SpeakerResponse:
    speaker = await container.get_speaker.execute(
        GetSpeakerQuery(actor=actor, speaker_id=speaker_id)
    )
    return to_speaker_response(speaker)


@router.post(
    "",
    response_model=SpeakerResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Crea un ponente (no necesita usuario)",
)
async def create_speaker(
    body: SpeakerCreateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SpeakerResponse:
    speaker = await container.create_speaker.execute(to_create_speaker_command(body, actor))
    return to_speaker_response(speaker)


@router.patch("/{speaker_id}", response_model=SpeakerResponse, responses=_ERRORS)
async def update_speaker(
    speaker_id: UUID,
    body: SpeakerUpdateRequest,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> SpeakerResponse:
    speaker = await container.update_speaker.execute(
        to_update_speaker_command(speaker_id, body, actor)
    )
    return to_speaker_response(speaker)


@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def delete_speaker(
    speaker_id: UUID,
    actor: User = Depends(current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.delete_speaker.execute(SpeakerActionCommand(actor=actor, speaker_id=speaker_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
