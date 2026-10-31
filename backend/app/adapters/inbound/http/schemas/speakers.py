from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SpeakerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    bio: str | None = Field(default=None, max_length=2000)


class SpeakerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    bio: str | None = Field(default=None, max_length=2000)


class SpeakerResponse(BaseModel):
    id: UUID
    name: str
    email: str | None
    bio: str | None
    created_by_id: UUID
    created_at: datetime


class SpeakerPage(BaseModel):
    items: list[SpeakerResponse]
    total: int
    page: int
    page_size: int
