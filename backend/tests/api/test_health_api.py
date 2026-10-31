def test_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_is_degraded_but_200_when_redis_is_down(make_client):
    response = make_client(redis_ok=False).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "checks": {"postgres": True, "redis": False}}


def test_readiness_is_503_when_postgres_is_down(make_client):
    response = make_client(postgres_ok=False).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_openapi_declares_the_cookie_security_scheme(client):
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert any(s["type"] == "apiKey" and s["in"] == "cookie" for s in schemes.values())
