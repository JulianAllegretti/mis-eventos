import re

from app.application.dto.policies import LoginRateLimit
from app.domain.models.event import EventStatus
from app.domain.models.user import Role
from tests.api.conftest import ALLOWED_ORIGIN
from tests.factories import make_event, make_user

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"
CREDS = {"email": "ana@example.com", "password": "secreto123"}


def _register(client):
    client.post(REGISTER, json={**CREDS, "full_name": "Ana"})


class TestLoginRateLimitApi:
    def _client(self, make_client):
        policy = LoginRateLimit(
            max_failures_per_email=3, max_failures_per_ip=50, window_seconds=900
        )
        client = make_client(login_policy=policy)
        _register(client)
        return client

    def test_blocks_with_429_retry_after_and_the_standard_error_body(self, make_client):
        client = self._client(make_client)
        for _ in range(3):
            assert client.post(LOGIN, json={**CREDS, "password": "mala"}).status_code == 401

        blocked = client.post(LOGIN, json=CREDS)  # incluso con la contraseña correcta

        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert blocked.json()["code"] == "too_many_attempts"
        assert "minuto" in blocked.json()["message"]
        assert "set-cookie" not in blocked.headers  # no se abrió sesión

    def test_a_blocked_account_does_not_leak_a_session(self, make_client):
        client = self._client(make_client)
        for _ in range(3):
            client.post(LOGIN, json={**CREDS, "password": "mala"})
        client.post(LOGIN, json=CREDS)
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_other_accounts_keep_working(self, make_client):
        client = self._client(make_client)
        client.post(
            REGISTER,
            json={"email": "luis@example.com", "password": "secreto123", "full_name": "Luis"},
        )
        for _ in range(3):
            client.post(LOGIN, json={**CREDS, "password": "mala"})

        assert (
            client.post(
                LOGIN, json={"email": "luis@example.com", "password": "secreto123"}
            ).status_code
            == 200
        )

    def test_429_is_documented_in_openapi(self, client):
        responses = client.get("/openapi.json").json()["paths"][LOGIN]["post"]["responses"]
        assert "429" in responses


class TestMetricsEndpoint:
    def test_exposes_prometheus_text_format(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "# HELP miseventos_http_requests_total" in response.text

    def test_is_not_part_of_the_public_api_docs(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert "/metrics" not in paths

    def test_labels_use_the_route_template_not_the_real_url(self, client, events, users):
        owner = make_user(Role.ORGANIZER)
        users[owner.id] = owner
        event = make_event(owner.id, status=EventStatus.PUBLISHED)
        events[event.id] = event

        client.get(f"/api/v1/events/{event.id}")
        client.get(f"/api/v1/events/{make_event(owner.id).id}")  # otro id: mismo patrón
        text = client.get("/metrics").text

        assert 'route="/api/v1/events/{event_id}"' in text
        assert str(event.id) not in text  # ningún id en las etiquetas

    def test_requests_and_latency_are_recorded(self, client):
        client.get("/health")
        text = client.get("/metrics").text

        assert re.search(
            r'miseventos_http_requests_total\{method="GET",route="/health",status="200"\} 1\.0',
            text,
        )
        assert (
            'miseventos_http_request_duration_seconds_bucket{le="0.005",method="GET",route="/health"}'
            in text
        )
        assert "miseventos_http_requests_in_flight" in text

    def test_unknown_urls_are_grouped_to_keep_cardinality_bounded(self, client):
        for i in range(5):
            client.get(f"/no-existe-{i}")
        text = client.get("/metrics").text

        assert 'route="unmatched",status="404"} 5.0' in text
        assert "no-existe" not in text

    def test_scraping_does_not_count_itself(self, client):
        client.get("/metrics")
        client.get("/metrics")
        assert 'route="/metrics"' not in client.get("/metrics").text

    def test_errors_are_counted_by_status(self, client):
        client.get("/api/v1/auth/me")  # 401
        assert 'route="/api/v1/auth/me",status="401"} 1.0' in client.get("/metrics").text

    def test_business_metrics_never_carry_personal_data(self, client, as_user):
        _register(client)
        client.post(LOGIN, json={**CREDS, "password": "incorrecta"})
        text = client.get("/metrics").text

        for secret in ("ana@example.com", "secreto123", "incorrecta", "access_token"):
            assert secret not in text


class TestLogsAreSafe:
    def test_request_log_has_a_fixed_set_of_non_sensitive_fields(self, client, monkeypatch):
        from app.adapters.inbound.http.middleware import request_context

        records = []

        class Recorder:
            def info(self, event, **fields):
                records.append((event, fields))

        monkeypatch.setattr(request_context, "log", Recorder())
        client.post(REGISTER, json={**CREDS, "full_name": "Ana"})
        client.post(LOGIN, json=CREDS, headers={"Origin": ALLOWED_ORIGIN})
        client.get("/api/v1/auth/me", headers={"X-Request-ID": "abc-123"})

        assert len(records) == 3
        for event, fields in records:
            assert event == "http_request"
            assert set(fields) == {"method", "path", "status", "duration_ms", "user_id"}
        rendered = repr(records)
        for secret in ("secreto123", "ana@example.com", "access_token", "Ana"):
            assert secret not in rendered

    def test_unexpected_errors_log_the_exception_type_not_its_message(
        self, make_client, monkeypatch
    ):
        from app.adapters.inbound.http import error_handlers

        records = []

        class Recorder:
            def error(self, event, **fields):
                records.append((event, fields))

        monkeypatch.setattr(error_handlers, "log", Recorder())
        from fastapi.testclient import TestClient

        base = make_client()
        container = base.app.state.container
        client = TestClient(
            base.app, raise_server_exceptions=False
        )  # devuelve el 500 en vez de relanzar

        async def explode(*_, **__):
            raise RuntimeError("fallo con ana@example.com y secreto123")

        container.register_user.execute = explode  # type: ignore[method-assign]
        response = client.post(REGISTER, json={**CREDS, "full_name": "Ana"})

        assert response.status_code == 500
        assert "secreto123" not in response.text  # el cliente tampoco ve el detalle
        ((event, fields),) = records
        assert event == "unhandled_error"
        assert fields["error"] == "RuntimeError"
