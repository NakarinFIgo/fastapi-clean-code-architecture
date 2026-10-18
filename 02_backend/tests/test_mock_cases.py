"""Scenario suite: what a person clicking through the UI would hit, against seeded mock data.

Each test name is the case id; the frontend has the same cases in 01_frontend/src/test/mock_cases.test.tsx.
"""

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app
from app.mock.data import ADMIN, MOCK_PASSWORD, NO_PERMISSION, VIEWER
from app.mock.seed import seed
from app.shared.security import TokenService, TokenType

API = "/api/v1"


@pytest.fixture
def mock_client(settings, session_factory) -> TestClient:
    with session_factory() as s:
        seed(s)
    return TestClient(create_app(settings, session_factory=session_factory))


def login(client, user=ADMIN, password=MOCK_PASSWORD):
    return client.post(f"{API}/login", json={"email": user.email, "password": password})


def bearer(res) -> dict[str, str]:
    return {"Authorization": f"Bearer {res.json()['token']['access']}"}


def test_mc01_admin_logs_in_and_sees_profile(mock_client):
    res = login(mock_client)
    assert res.status_code == 200
    profile = mock_client.post(f"{API}/profile", headers=bearer(res))
    assert profile.json()["email"] == ADMIN.email
    assert profile.json()["first_name"] == "Admin"


def test_mc02_wrong_password(mock_client):
    res = login(mock_client, password="nope")
    assert (res.status_code, res.json()) == (
        400,
        {"trace_id": "users-002", "message": "password is invalid"},
    )


def test_mc03_unknown_user(mock_client):
    res = mock_client.post(f"{API}/login", json={"email": "ghost@example.com", "password": "x"})
    assert (res.status_code, res.json()["message"]) == (400, "record not found")


@pytest.mark.parametrize("email", ["plainaddress", "a@b", "a@b.museum"])
def test_mc04_register_with_bad_email(mock_client, email):
    res = mock_client.post(f"{API}/register", json={"email": email, "password": "pw"})
    assert (res.status_code, res.json()["trace_id"]) == (400, "users-001")


def test_mc05_register_with_password_over_72_bytes(mock_client):
    res = mock_client.post(
        f"{API}/register", json={"email": "long@example.com", "password": "x" * 73}
    )
    assert res.status_code == 500
    assert "72 bytes" in res.json()["message"]


def test_mc06_register_duplicate_email(mock_client):
    res = mock_client.post(f"{API}/register", json={"email": ADMIN.email, "password": "whatever"})
    assert (res.status_code, res.json()["trace_id"]) == (500, "users-001")


def test_mc07_new_user_can_register_then_log_in(mock_client):
    body = {"email": "new@example.com", "password": "pw123456"}
    assert mock_client.post(f"{API}/register", json=body).status_code == 201
    assert mock_client.post(f"{API}/login", json=body).status_code == 200


def test_mc08_expired_access_token(mock_client, settings):
    res = login(mock_client)
    user_id = res.json()["user"]["id"]
    expired = TokenService(settings).sign(
        TokenType.ACCESS, user_id, expires_at=int(time.time()) - 10
    )
    out = mock_client.post(f"{API}/profile", headers={"Authorization": f"Bearer {expired}"})
    assert (out.status_code, out.json()["message"]) == (401, "token had expired")


def test_mc09_tampered_token(mock_client):
    token = login(mock_client).json()["token"]["access"]
    tampered = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    out = mock_client.post(f"{API}/profile", headers={"Authorization": f"Bearer {tampered}"})
    assert out.status_code == 401
    assert out.json()["trace_id"] == "middlware-002"


def test_mc10_old_token_is_revoked_by_a_newer_login(mock_client, monkeypatch):
    first = login(mock_client)
    # iat has 1s resolution; move the clock BACK (a future nbf would be rejected on decode)
    earlier = int(time.time()) - 5
    monkeypatch.setattr("app.shared.security.time", SimpleNamespace(time=lambda: earlier))
    second = login(mock_client)

    assert first.json()["token"]["access"] != second.json()["token"]["access"]
    assert mock_client.post(f"{API}/profile", headers=bearer(first)).status_code == 401
    assert mock_client.post(f"{API}/profile", headers=bearer(second)).status_code == 200


def test_mc11_refresh_rotates_access_token(mock_client, monkeypatch):
    first = login(mock_client)
    earlier = int(time.time()) - 5
    monkeypatch.setattr("app.shared.security.time", SimpleNamespace(time=lambda: earlier))
    out = mock_client.post(
        f"{API}/refresh-token", json={"refresh_token": first.json()["token"]["refresh"]}
    )
    assert out.status_code == 200
    assert mock_client.post(f"{API}/profile", headers=bearer(out)).status_code == 200


def test_mc12_access_token_cannot_be_used_to_refresh(mock_client):
    first = login(mock_client)
    out = mock_client.post(
        f"{API}/refresh-token", json={"refresh_token": first.json()["token"]["access"]}
    )
    assert (out.status_code, out.json()["trace_id"]) == (400, "users-003")


def test_mc13_logout_kills_the_session(mock_client):
    first = login(mock_client)
    out = mock_client.post(
        f"{API}/logout", json={"refresh_token": first.json()["token"]["refresh"]}
    )
    assert out.status_code == 200
    assert mock_client.post(f"{API}/profile", headers=bearer(first)).status_code == 401


def test_mc14_user_without_permission_row_can_still_browse(mock_client):
    res = login(mock_client, NO_PERMISSION)
    out = mock_client.get(f"{API}/data/users/", headers=bearer(res))
    assert out.status_code == 200
    assert {u["email"] for u in out.json()["data"]} >= {ADMIN.email, VIEWER.email}


def test_mc15_admin_pages_through_permissions(mock_client):
    headers = bearer(login(mock_client))
    page2 = mock_client.get(f"{API}/data/user-permissions/?_page=2&_pageSize=10", headers=headers)
    page3 = mock_client.get(f"{API}/data/user-permissions/?_page=3&_pageSize=10", headers=headers)
    page4 = mock_client.get(f"{API}/data/user-permissions/?_page=4&_pageSize=10", headers=headers)

    # 27 rows (admin 1 + 25 extra, viewer 1): 10 + 10 + 7, then empty
    assert [len(p.json()["data"]) for p in (page2, page3, page4)] == [10, 7, 0]


@pytest.mark.parametrize("qs", ["_pageSize=-1", "_pageSize=0", "_pageSize=x", "_page=0", "_page=x"])
def test_mc16_odd_pagination_values_fall_back_to_defaults(mock_client, qs):
    out = mock_client.get(f"{API}/data/users/?{qs}", headers=bearer(login(mock_client)))
    assert out.status_code == 200
    assert (out.json()["page"], out.json()["page_size"]) == (1, 10)


def test_mc17_unknown_collection(mock_client):
    out = mock_client.get(f"{API}/data/widgets/", headers=bearer(login(mock_client)))
    assert (out.status_code, out.json()["message"]) == (400, "Entity model not found")


def test_mc18_tokens_table_is_not_browsable(mock_client):
    out = mock_client.get(f"{API}/data/user-tokens/", headers=bearer(login(mock_client)))
    assert out.status_code == 400


def test_mc19_password_is_never_returned(mock_client):
    out = mock_client.get(f"{API}/data/users/", headers=bearer(login(mock_client)))
    assert all("password" not in u for u in out.json()["data"])
