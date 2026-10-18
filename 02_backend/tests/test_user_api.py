import pytest

BASE = "/api/v1"
CREDS = {
    "email": "ann@example.com",
    "password": "pw123456",
    "first_name": "Ann",
    "last_name": "Lee",
}


def register(client, **overrides):
    return client.post(f"{BASE}/register", json={**CREDS, **overrides})


def login(client):
    return client.post(
        f"{BASE}/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_201_bare_entity(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "email", "first_name", "last_name", "created_at", "updated_at"}
    assert "password" not in body


def test_register_bad_email_400_users_001(client):
    r = register(client, email="nope")
    assert r.status_code == 400
    assert r.json() == {"trace_id": "users-001", "message": "email pattern is invalid"}


def test_register_malformed_body_400_users_001(client):
    r = client.post(f"{BASE}/register", json={"email": "a@b.co"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-001"


def test_register_long_password_500_like_go(client):
    r = register(client, password="x" * 80)
    assert r.status_code == 500
    assert r.json()["trace_id"] == "users-001"
    assert "72 bytes" in r.json()["message"]


def test_register_duplicate_500_like_go(client):
    register(client)
    r = register(client)
    assert r.status_code == 500
    assert r.json()["trace_id"] == "users-001"


def test_login_shape(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"user", "token"}
    assert set(body["token"]) == {"access", "refresh"}


def test_login_wrong_password_400_users_002(client):
    register(client)
    r = client.post(f"{BASE}/login", json={"email": CREDS["email"], "password": "bad"})
    assert r.status_code == 400
    assert r.json() == {"trace_id": "users-002", "message": "password is invalid"}


def test_profile_requires_valid_token(client):
    register(client)
    token = login(client).json()["token"]["access"]
    r = client.post(f"{BASE}/profile", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == CREDS["email"]


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "bearer abc"},
        {"Authorization": "Bearer abc"},
        {"Authorization": "Basic abc"},
    ],
)
def test_profile_bad_auth_header_is_401_envelope(client, headers):
    r = client.post(f"{BASE}/profile", headers=headers)
    assert r.status_code == 401
    body = r.json()
    assert body["trace_id"] == "middlware-002"
    assert body["message"]


def test_refresh_flow(client):
    register(client)
    tokens = login(client).json()["token"]
    r = client.post(f"{BASE}/refresh-token", json={"refresh_token": tokens["refresh"]})
    assert r.status_code == 200
    new_access = r.json()["token"]["access"]
    assert client.post(f"{BASE}/profile", headers=auth(new_access)).status_code == 200


def test_refresh_bad_token_400_users_003(client):
    r = client.post(f"{BASE}/refresh-token", json={"refresh_token": "abc"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-003"


def test_logout_then_profile_401(client):
    register(client)
    tokens = login(client).json()["token"]
    r = client.post(f"{BASE}/logout", json={"refresh_token": tokens["refresh"]})
    assert r.status_code == 200
    assert client.post(f"{BASE}/profile", headers=auth(tokens["access"])).status_code == 401


def test_logout_bad_token_400_users_004(client):
    r = client.post(f"{BASE}/logout", json={"refresh_token": "abc"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-004"
