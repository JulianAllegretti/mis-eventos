"""Serialización JSON de eventos para la caché de lectura."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.dto.read_models import Page
from app.domain.models.event import ClosedSource, Event, EventStatus

_DATETIME_FIELDS = ("start_at", "end_at", "created_at", "updated_at", "closed_at")


def _event_to_dict(event: Event) -> dict[str, Any]:
    raw = asdict(event)
    for key in ("id", "organizer_id", "closed_by_id"):
        raw[key] = str(raw[key]) if raw[key] is not None else None
    for key in _DATETIME_FIELDS:
        raw[key] = raw[key].isoformat() if raw[key] is not None else None
    raw["status"] = event.status.value
    raw["closed_source"] = event.closed_source.value if event.closed_source else None
    return raw


def _event_from_dict(raw: dict[str, Any]) -> Event:
    data = dict(raw)
    for key in ("id", "organizer_id", "closed_by_id"):
        data[key] = UUID(data[key]) if data[key] is not None else None
    for key in _DATETIME_FIELDS:
        data[key] = datetime.fromisoformat(data[key]) if data[key] is not None else None
    data["status"] = EventStatus(data["status"])
    data["closed_source"] = ClosedSource(data["closed_source"]) if data["closed_source"] else None
    return Event(**data)


def encode_event(event: Event) -> str:
    return json.dumps(_event_to_dict(event))


def decode_event(payload: str) -> Event:
    return _event_from_dict(json.loads(payload))


def encode_page(page: Page[Event]) -> str:
    return json.dumps(
        {
            "items": [_event_to_dict(e) for e in page.items],
            "total": page.total,
            "page": page.page,
            "page_size": page.page_size,
        }
    )


def decode_page(payload: str) -> Page[Event]:
    raw = json.loads(payload)
    return Page(
        items=[_event_from_dict(e) for e in raw["items"]],
        total=raw["total"],
        page=raw["page"],
        page_size=raw["page_size"],
    )
