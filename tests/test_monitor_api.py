from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


def test_health_check(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/")
    assert r.status_code == 200
    assert r.json() == {"name": "GOLANG FIRST API APP", "version": "0.0.1"}


def test_unknown_route_uses_error_envelope(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json() == {"trace_id": "middlware-001", "message": "rotuer not found"}


def test_cors_allows_any_origin(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/", headers={"Origin": "http://x.test"})
    assert r.headers["access-control-allow-origin"] == "*"
