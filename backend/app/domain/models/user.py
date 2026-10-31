from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from app.domain.services.credentials import normalize_email


class Role(StrEnum):
    ATTENDEE = "attendee"
    ORGANIZER = "organizer"
    ADMIN = "admin"


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime

    @classmethod
    def new(
        cls,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        now: datetime,
        role: Role = Role.ATTENDEE,
    ) -> Self:
        return cls(
            id=uuid4(),
            email=normalize_email(email),
            password_hash=password_hash,
            full_name=full_name.strip(),
            role=role,
            is_active=True,
            created_at=now,
        )
