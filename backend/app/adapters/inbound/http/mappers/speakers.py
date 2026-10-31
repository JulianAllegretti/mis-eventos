from uuid import UUID

from app.adapters.inbound.http.schemas.speakers import (
    SpeakerCreateRequest,
    SpeakerPage,
    SpeakerResponse,
    SpeakerUpdateRequest,
)
from app.application.dto.commands import CreateSpeakerCommand, UpdateSpeakerCommand
from app.application.dto.read_models import Page
from app.domain.models.speaker import Speaker
from app.domain.models.user import User


def to_create_speaker_command(body: SpeakerCreateRequest, actor: User) -> CreateSpeakerCommand:
    return CreateSpeakerCommand(actor=actor, name=body.name, email=body.email, bio=body.bio)


def to_update_speaker_command(
    speaker_id: UUID, body: SpeakerUpdateRequest, actor: User
) -> UpdateSpeakerCommand:
    return UpdateSpeakerCommand(
        actor=actor, speaker_id=speaker_id, changes=body.model_dump(exclude_unset=True)
    )


def to_speaker_response(speaker: Speaker) -> SpeakerResponse:
    return SpeakerResponse(
        id=speaker.id,
        name=speaker.name,
        email=speaker.email,
        bio=speaker.bio,
        created_by_id=speaker.created_by_id,
        created_at=speaker.created_at,
    )


def to_speaker_page(page: Page[Speaker]) -> SpeakerPage:
    return SpeakerPage(
        items=[to_speaker_response(s) for s in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
