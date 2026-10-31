from datetime import timedelta

from app.domain.models.event import EventStatus
from app.domain.models.user import Role
from tests.api.conftest import when
from tests.factories import make_event, make_user

URL = "/api/v1/events"


def _body(**overrides):
    base = {
        "name": "Congreso de Tecnología",
        "description": "Tres días de charlas",
        "location": "Bogotá",
        "start_at": when(days=5),
        "end_at": when(days=5, hours=6),
        "capacity": 80,
    }
    return {**base, **overrides}


def _seed(events, organizer_id, **kwargs):
    event = make_event(organizer_id, **kwargs)
    events[event.id] = event
    return event


class TestCreate:
    def test_organizer_creates_a_draft(self, client, as_user):
        organizer = as_user(Role.ORGANIZER)

        response = client.post(URL, json=_body())

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "draft"
        assert body["organizer_id"] == str(organizer.id)
        assert body["registered_count"] == 0
        assert body["available_slots"] == 80
        assert body["closed_at"] is None

    def test_anonymous_gets_401_and_attendee_gets_403(self, client, as_user):
        assert client.post(URL, json=_body()).status_code == 401
        as_user(Role.ATTENDEE)
        assert client.post(URL, json=_body()).status_code == 403

    def test_validation_errors_use_the_standard_envelope(self, client, as_user):
        as_user(Role.ORGANIZER)

        response = client.post(URL, json=_body(capacity=0, name=""))

        assert response.status_code == 422
        assert response.json()["code"] == "validation_failed"
        assert response.json()["details"]

    def test_domain_validation_reports_all_problems(self, client, as_user):
        as_user(Role.ORGANIZER)

        response = client.post(URL, json=_body(start_at=when(days=-1), end_at=when(days=-2)))

        assert response.status_code == 422
        assert len(response.json()["details"]) == 2

    def test_datetime_without_timezone_is_rejected(self, client, as_user):
        as_user(Role.ORGANIZER)
        naive = (_body()["start_at"]).split("+")[0]
        assert client.post(URL, json=_body(start_at=naive)).status_code == 422


class TestRead:
    def test_public_list_shows_published_only_and_paginates(self, client, events):
        owner = make_user(Role.ORGANIZER)
        for i in range(1, 4):
            _seed(
                events,
                owner.id,
                name=f"Evento {i}",
                status=EventStatus.PUBLISHED,
                starts_in=timedelta(days=i),
            )
        _seed(events, owner.id, name="Borrador")

        response = client.get(URL, params={"page": 2, "page_size": 2})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert (body["page"], body["page_size"]) == (2, 2)
        assert [e["name"] for e in body["items"]] == ["Evento 3"]

    def test_search_by_part_of_the_name(self, client, events):
        owner = make_user(Role.ORGANIZER)
        _seed(events, owner.id, name="Congreso de Python", status=EventStatus.PUBLISHED)
        _seed(events, owner.id, name="Charla de Rust", status=EventStatus.PUBLISHED)

        response = client.get(URL, params={"q": "pyth"})

        assert [e["name"] for e in response.json()["items"]] == ["Congreso de Python"]

    def test_page_size_above_50_is_rejected(self, client):
        assert client.get(URL, params={"page_size": 51}).status_code == 422

    def test_scope_mine_requires_a_session_and_shows_own_drafts(self, client, as_user, events):
        assert client.get(URL, params={"scope": "mine"}).status_code == 422
        me = as_user(Role.ORGANIZER)
        _seed(events, me.id, name="Mi borrador")
        _seed(events, make_user(Role.ORGANIZER).id, name="Ajeno")

        response = client.get(URL, params={"scope": "mine"})

        assert [e["name"] for e in response.json()["items"]] == ["Mi borrador"]

    def test_draft_is_hidden_from_anonymous_and_other_organizers(self, client, as_user, events):
        owner = make_user(Role.ORGANIZER)
        draft = _seed(events, owner.id)
        assert client.get(f"{URL}/{draft.id}").status_code == 404
        as_user(Role.ORGANIZER)
        assert client.get(f"{URL}/{draft.id}").status_code == 404

    def test_owner_and_admin_can_read_a_draft(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        draft = _seed(events, owner.id)
        assert client.get(f"{URL}/{draft.id}").status_code == 200
        as_user(Role.ADMIN)
        assert client.get(f"{URL}/{draft.id}").status_code == 200

    def test_published_event_in_the_past_is_reported_as_finished(self, client, events):
        owner = make_user(Role.ORGANIZER)
        old = _seed(events, owner.id, status=EventStatus.PUBLISHED, starts_in=-timedelta(days=3))

        assert client.get(f"{URL}/{old.id}").json()["status"] == "finished"

    def test_unknown_or_malformed_id(self, client):
        assert client.get(f"{URL}/00000000-0000-0000-0000-000000000000").status_code == 404
        assert client.get(f"{URL}/no-es-uuid").status_code == 422


class TestUpdateAndTransitions:
    def test_partial_update_keeps_other_fields(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id)

        response = client.patch(f"{URL}/{event.id}", json={"capacity": 150})

        assert response.status_code == 200
        assert response.json()["capacity"] == 150
        assert response.json()["name"] == event.name

    def test_cannot_set_protected_fields(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id)

        response = client.patch(
            f"{URL}/{event.id}", json={"status": "finished", "registered_count": 0}
        )

        assert response.status_code == 200  # los campos extra se ignoran por el esquema
        assert response.json()["status"] == "draft"

    def test_other_organizer_gets_403_on_a_published_event(self, client, as_user, events):
        owner = make_user(Role.ORGANIZER)
        event = _seed(events, owner.id, status=EventStatus.PUBLISHED)
        as_user(Role.ORGANIZER)

        assert client.patch(f"{URL}/{event.id}", json={"name": "X"}).status_code == 403
        assert client.post(f"{URL}/{event.id}/cancel").status_code == 403

    def test_full_lifecycle(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id)

        published = client.post(f"{URL}/{event.id}/publish")
        assert published.json()["status"] == "published"
        assert client.post(f"{URL}/{event.id}/publish").status_code == 409

        finished = client.post(f"{URL}/{event.id}/finish").json()
        assert finished["status"] == "finished"
        assert finished["closed_source"] == "manual"
        assert finished["closed_by_id"] == str(owner.id)
        assert finished["closed_at"] is not None

        assert client.post(f"{URL}/{event.id}/cancel").status_code == 409
        assert client.patch(f"{URL}/{event.id}", json={"name": "X"}).status_code == 409

    def test_cancel_a_published_event(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id, status=EventStatus.PUBLISHED)

        body = client.post(f"{URL}/{event.id}/cancel").json()

        assert (body["status"], body["closed_source"]) == ("cancelled", "manual")

    def test_delete_without_registrations(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id)

        assert client.delete(f"{URL}/{event.id}").status_code == 204
        assert events == {}

    def test_delete_with_registrations_is_409(self, client, as_user, events):
        owner = as_user(Role.ORGANIZER)
        event = _seed(events, owner.id, status=EventStatus.PUBLISHED, registered=2)

        assert client.delete(f"{URL}/{event.id}").status_code == 409
        assert event.id in events

    def test_mutations_require_a_session(self, client, events):
        event = _seed(events, make_user(Role.ORGANIZER).id, status=EventStatus.PUBLISHED)
        for method, path in (
            ("patch", f"{URL}/{event.id}"),
            ("delete", f"{URL}/{event.id}"),
            ("post", f"{URL}/{event.id}/publish"),
            ("post", f"{URL}/{event.id}/finish"),
            ("post", f"{URL}/{event.id}/cancel"),
        ):
            assert getattr(client, method)(path).status_code == 401
