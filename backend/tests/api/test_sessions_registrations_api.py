from datetime import timedelta

import pytest

from app.domain.models.event import EventStatus
from app.domain.models.user import Role
from tests.api.conftest import when
from tests.factories import make_event, make_speaker, make_user

EVENTS = "/api/v1/events"
SESSIONS = "/api/v1/sessions"
EVENT_START_DAYS = 10  # make_event: empieza en 10 días y dura 8 horas


def _hour(h: float) -> str:
    return when(days=EVENT_START_DAYS, hours=h)


@pytest.fixture
def world(events, speakers, users):
    owner = make_user(Role.ORGANIZER)
    users[owner.id] = owner
    event = make_event(owner.id, status=EventStatus.PUBLISHED, capacity=2)
    events[event.id] = event
    speaker = make_speaker(owner.id)
    speakers[speaker.id] = speaker
    return owner, event, speaker


def _session_body(speaker, start=1, end=2, **overrides):
    return {
        "speaker_id": str(speaker.id),
        "title": "Introducción a FastAPI",
        "start_at": _hour(start),
        "end_at": _hour(end),
        "capacity": 2,
        **overrides,
    }


class TestSessionsApi:
    def test_owner_builds_the_agenda_and_everyone_can_read_it(self, client, as_user, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"

        created = client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker, 3, 4))
        assert created.status_code == 201
        client.post(
            f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker, 1, 2, title="Primera")
        )
        client.cookies.clear()

        agenda = client.get(f"{EVENTS}/{event.id}/sessions").json()

        assert [s["title"] for s in agenda] == ["Primera", "Introducción a FastAPI"]
        assert agenda[0]["speaker"] == {"id": str(speaker.id), "name": speaker.name, "bio": "Bio"}
        assert "email" not in agenda[0]["speaker"]  # el correo del ponente no es público
        assert agenda[0]["available_slots"] == 2

    def test_overlapping_speaker_is_409(self, client, as_user, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"
        client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker, 1, 3))

        clash = client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker, 2, 4))

        assert clash.status_code == 409
        assert clash.json()["code"] == "schedule_conflict"

    def test_session_outside_the_event_is_422(self, client, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"

        response = client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker, -2, 1))

        assert response.status_code == 422
        assert "dentro del horario" in response.json()["details"][0]

    def test_permissions(self, client, as_user, world):
        _, event, speaker = world
        assert (
            client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker)).status_code
            == 401
        )
        as_user(Role.ATTENDEE)
        assert (
            client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker)).status_code
            == 403
        )
        as_user(Role.ORGANIZER)  # otro organizador
        assert (
            client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker)).status_code
            == 403
        )

    def test_update_and_delete(self, client, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"
        session_id = client.post(
            f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker)
        ).json()["id"]

        patched = client.patch(f"{SESSIONS}/{session_id}", json={"title": "Otro", "capacity": 1})
        assert (patched.json()["title"], patched.json()["capacity"]) == ("Otro", 1)
        assert client.delete(f"{SESSIONS}/{session_id}").status_code == 204
        assert client.get(f"{EVENTS}/{event.id}/sessions").json() == []

    def test_speaker_with_sessions_cannot_be_deleted(self, client, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"
        client.post(f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker))

        assert client.delete(f"/api/v1/speakers/{speaker.id}").status_code == 409


class TestRegistrationsApi:
    def test_full_attendee_journey(self, client, as_user, world):
        owner, event, speaker = world
        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        client.headers["Origin"] = "http://localhost:5173"
        session_id = client.post(
            f"{EVENTS}/{event.id}/sessions", json=_session_body(speaker)
        ).json()["id"]
        as_user(Role.ATTENDEE)

        # no puede inscribirse a la sesión sin estar en el evento
        assert client.post(f"{SESSIONS}/{session_id}/registrations").status_code == 409

        joined = client.post(f"{EVENTS}/{event.id}/registrations")
        assert joined.status_code == 201
        assert client.post(f"{EVENTS}/{event.id}/registrations").status_code == 409
        assert client.post(f"{SESSIONS}/{session_id}/registrations").status_code == 201

        mine = client.get("/api/v1/users/me/registrations").json()
        assert [r["event"]["id"] for r in mine] == [str(event.id)]
        assert mine[0]["event"]["registered_count"] == 1
        assert [s["id"] for s in mine[0]["sessions"]] == [session_id]

        assert client.delete(f"{EVENTS}/{event.id}/registrations/me").status_code == 204
        assert client.get("/api/v1/users/me/registrations").json() == []
        assert client.get(f"{EVENTS}/{event.id}").json()["registered_count"] == 0

    def test_event_full_is_409_with_a_stable_code(self, client, as_user, world):
        _, event, _ = world
        for _ in range(2):
            as_user(Role.ATTENDEE)
            assert client.post(f"{EVENTS}/{event.id}/registrations").status_code == 201
        as_user(Role.ATTENDEE)

        response = client.post(f"{EVENTS}/{event.id}/registrations")

        assert response.status_code == 409
        assert response.json()["code"] == "event_full"
        assert client.get(f"{EVENTS}/{event.id}").json()["available_slots"] == 0

    def test_registration_requires_a_session(self, client, world):
        _, event, _ = world
        assert client.post(f"{EVENTS}/{event.id}/registrations").status_code == 401
        assert client.get("/api/v1/users/me/registrations").status_code == 401

    def test_draft_and_unknown_events(self, client, as_user, events, world):
        owner, _, _ = world
        draft = make_event(owner.id)
        events[draft.id] = draft
        as_user(Role.ATTENDEE)
        assert client.post(f"{EVENTS}/{draft.id}/registrations").status_code == 404
        assert (
            client.post(f"{EVENTS}/00000000-0000-0000-0000-000000000000/registrations").status_code
            == 404
        )

    def test_finished_events_reject_registrations(self, client, as_user, events, world):
        owner, _, _ = world
        old = make_event(owner.id, status=EventStatus.PUBLISHED, starts_in=-timedelta(days=3))
        events[old.id] = old
        as_user(Role.ATTENDEE)
        response = client.post(f"{EVENTS}/{old.id}/registrations")
        assert response.status_code == 409
        assert response.json()["code"] == "invalid_transition"

    def test_attendee_list_is_for_owner_and_admin_only(self, client, as_user, world):
        owner, event, _ = world
        attendee = as_user(Role.ATTENDEE)
        client.post(f"{EVENTS}/{event.id}/registrations")
        assert client.get(f"{EVENTS}/{event.id}/registrations").status_code == 403

        client.cookies.set("access_token", f"token:{owner.id}:organizer")
        listing = client.get(f"{EVENTS}/{event.id}/registrations").json()

        assert listing["total"] == 1
        assert listing["items"][0]["user_id"] == str(attendee.id)

    def test_cancelling_requires_an_active_registration(self, client, as_user, world):
        _, event, _ = world
        as_user(Role.ATTENDEE)
        assert client.delete(f"{EVENTS}/{event.id}/registrations/me").status_code == 404

    def test_registration_endpoints_are_protected_against_foreign_origins(
        self, client, as_user, world
    ):
        _, event, _ = world
        as_user(Role.ATTENDEE)
        response = client.post(
            f"{EVENTS}/{event.id}/registrations", headers={"Origin": "https://evil.example"}
        )
        assert response.status_code == 403
