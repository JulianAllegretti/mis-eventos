from tests.api.conftest import ALLOWED_ORIGIN

REGISTER = {"email": "ana@example.com", "password": "secreto123", "full_name": "Ana"}
LOGIN = {"email": "ana@example.com", "password": "secreto123"}
PREFIX = "/api/v1/auth"


def _login(client):
    assert client.post(f"{PREFIX}/register", json=REGISTER).status_code == 201
    response = client.post(f"{PREFIX}/login", json=LOGIN)
    assert response.status_code == 200
    return response


def test_register_returns_user_without_secrets(client):
    response = client.post(f"{PREFIX}/register", json=REGISTER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert body["role"] == "attendee"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_is_409(client):
    client.post(f"{PREFIX}/register", json=REGISTER)
    response = client.post(f"{PREFIX}/register", json=REGISTER)

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_register_cannot_choose_a_role(client):
    response = client.post(f"{PREFIX}/register", json={**REGISTER, "role": "admin"})

    assert response.status_code == 201
    assert response.json()["role"] == "attendee"


def test_register_validation_error_does_not_echo_the_password(client):
    response = client.post(f"{PREFIX}/register", json={**REGISTER, "password": "corta"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert "corta" not in response.text


def test_login_sets_httponly_cookie_and_does_not_return_the_token(client):
    response = _login(client)

    cookie = response.headers["set-cookie"].lower()
    assert "access_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "token" not in response.json()


def test_login_failures_use_the_same_generic_response(client):
    client.post(f"{PREFIX}/register", json=REGISTER)

    wrong_password = client.post(f"{PREFIX}/login", json={**LOGIN, "password": "incorrecta1"})
    unknown_email = client.post(f"{PREFIX}/login", json={**LOGIN, "email": "otro@example.com"})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_me_requires_a_session(client):
    assert client.get(f"{PREFIX}/me").status_code == 401


def test_me_returns_the_logged_in_user(client):
    _login(client)

    response = client.get(f"{PREFIX}/me")

    assert response.status_code == 200
    assert response.json()["email"] == "ana@example.com"


def test_me_rejects_a_forged_cookie(client):
    client.cookies.set("access_token", "no-es-un-token")
    assert client.get(f"{PREFIX}/me").status_code == 401


def test_logout_clears_the_session(client):
    _login(client)

    response = client.post(f"{PREFIX}/logout", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 204
    assert client.get(f"{PREFIX}/me").status_code == 401


def test_state_changing_request_with_cookie_from_foreign_origin_is_rejected(client):
    _login(client)

    response = client.post(f"{PREFIX}/logout", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"
    assert client.get(f"{PREFIX}/me").status_code == 200  # la sesión sigue activa


def test_state_changing_request_with_cookie_and_no_origin_is_rejected(client):
    _login(client)
    assert client.post(f"{PREFIX}/logout").status_code == 403


def test_referer_is_accepted_when_origin_is_missing(client):
    _login(client)

    response = client.post(f"{PREFIX}/logout", headers={"Referer": f"{ALLOWED_ORIGIN}/profile"})

    assert response.status_code == 204


def test_login_without_cookie_is_not_subject_to_origin_check(client):
    client.post(f"{PREFIX}/register", json=REGISTER)
    response = client.post(
        f"{PREFIX}/login", json=LOGIN, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 200


def test_responses_carry_a_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"

    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32

    unsafe = client.get("/health", headers={"X-Request-ID": "con espacios {y} llaves"})
    assert unsafe.headers["x-request-id"] != "con espacios {y} llaves"
