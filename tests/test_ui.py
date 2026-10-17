from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


def make_client(settings, session_factory, dist) -> TestClient:
    settings.goapp_frontend_dist = str(dist)
    return TestClient(create_app(settings, session_factory=session_factory))


def test_ui_is_served_without_login(settings, session_factory, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Sati UI</title>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    client = make_client(settings, session_factory, tmp_path)

    page = client.get("/ui/")
    assert page.status_code == 200
    assert "Sati UI" in page.text
    assert client.get("/ui/app.js").status_code == 200


def test_api_keeps_working_when_frontend_is_not_built(settings, session_factory, tmp_path):
    client = make_client(settings, session_factory, tmp_path / "does-not-exist")

    assert client.get("/ui/").status_code == 404
    assert client.get("/api/v1/").status_code == 200


def test_ui_mount_does_not_shadow_api_routes(settings, session_factory, tmp_path):
    (tmp_path / "index.html").write_text("x")
    client = make_client(settings, session_factory, tmp_path)

    assert client.get("/api/v1/").json()["name"] == settings.goapp_name
    assert client.get("/api/v1/nope").json()["trace_id"] == "middlware-001"
