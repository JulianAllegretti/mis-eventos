from app.domain.models.user import Role
from tests.factories import make_speaker, make_user

SPEAKERS = "/api/v1/speakers"
ADMIN = "/api/v1/admin/users"


class TestSpeakers:
    def test_organizer_manages_speakers_without_user_accounts(self, client, as_user):
        as_user(Role.ORGANIZER)

        created = client.post(SPEAKERS, json={"name": "Ana Pérez", "email": "ana@ponentes.co"})
        assert created.status_code == 201
        speaker_id = created.json()["id"]

        assert client.get(f"{SPEAKERS}/{speaker_id}").json()["name"] == "Ana Pérez"
        patched = client.patch(f"{SPEAKERS}/{speaker_id}", json={"bio": "Ingeniera"})
        assert patched.json()["bio"] == "Ingeniera"
        assert client.get(SPEAKERS, params={"q": "pér"}).json()["total"] == 1
        assert client.delete(f"{SPEAKERS}/{speaker_id}").status_code == 204
        assert client.get(f"{SPEAKERS}/{speaker_id}").status_code == 404

    def test_attendee_and_anonymous_are_rejected(self, client, as_user):
        assert client.get(SPEAKERS).status_code == 401
        as_user(Role.ATTENDEE)
        assert client.get(SPEAKERS).status_code == 403
        assert client.post(SPEAKERS, json={"name": "Ana"}).status_code == 403

    def test_invalid_email_is_422(self, client, as_user):
        as_user(Role.ORGANIZER)
        assert client.post(SPEAKERS, json={"name": "Ana", "email": "malo"}).status_code == 422

    def test_speaker_created_by_is_the_actor(self, client, as_user, speakers):
        organizer = as_user(Role.ORGANIZER)
        client.post(SPEAKERS, json={"name": "Luis"})
        (speaker,) = speakers.values()
        assert speaker.created_by_id == organizer.id
        assert make_speaker(organizer.id).created_by_id == organizer.id


class TestAdminUsers:
    def test_admin_lists_and_promotes_a_user(self, client, as_user, users):
        target = make_user(Role.ATTENDEE, email="juan@example.com")
        users[target.id] = target
        as_user(Role.ADMIN)

        listing = client.get(ADMIN, params={"q": "juan"}).json()
        assert [u["email"] for u in listing["items"]] == ["juan@example.com"]
        assert "password_hash" not in listing["items"][0]

        patched = client.patch(f"{ADMIN}/{target.id}", json={"role": "organizer"})
        assert patched.status_code == 200
        assert patched.json()["role"] == "organizer"

    def test_non_admins_are_rejected(self, client, as_user):
        assert client.get(ADMIN).status_code == 401
        as_user(Role.ORGANIZER)
        assert client.get(ADMIN).status_code == 403

    def test_admin_cannot_demote_themselves(self, client, as_user):
        admin = as_user(Role.ADMIN)
        response = client.patch(f"{ADMIN}/{admin.id}", json={"role": "attendee"})
        assert response.status_code == 403

    def test_deactivated_user_loses_access_immediately(self, client, as_user, users, make_client):
        admin = as_user(Role.ADMIN)
        victim = as_user(Role.ORGANIZER)  # inicia sesión como la víctima
        # el admin la desactiva: reutilizamos el mismo almacén de usuarios
        users[victim.id].is_active = False
        assert client.get("/api/v1/auth/me").status_code == 401
        assert admin.id != victim.id

    def test_unknown_role_is_422(self, client, as_user, users):
        target = make_user()
        users[target.id] = target
        as_user(Role.ADMIN)
        assert client.patch(f"{ADMIN}/{target.id}", json={"role": "root"}).status_code == 422
