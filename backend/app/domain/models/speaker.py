from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4


@dataclass(slots=True)
class Speaker:
    id: UUID
    name: str
    email: str | None
    bio: str | None
    created_by_id: UUID
    created_at: datetime

    @classmethod
    def new(
        cls,
        *,
        name: str,
        email: str | None,
        bio: str | None,
        created_by_id: UUID,
        now: datetime,
    ) -> Self:
        return cls(
            id=uuid4(),
            name=name,
            email=email,
            bio=bio,
            created_by_id=created_by_id,
            created_at=now,
        )
