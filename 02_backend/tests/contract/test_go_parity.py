"""Compare this service with the Go original running against the SAME Postgres.

    GO_URL=http://127.0.0.1:3000 PY_URL=http://127.0.0.1:3001 pytest -m contract tests/contract

Both servers must share GOAPP_SECRET_KEY and GOAPP_NAME, otherwise tokens and `iss` differ.
Skipped unless GO_URL and PY_URL are set.
"""

import os
import uuid

import httpx
import pytest

GO = os.environ.get("GO_URL", "")
PY = os.environ.get("PY_URL", "")
pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not (GO and PY), reason="set GO_URL and PY_URL"),
]


def shape(value):
    """Reduce JSON to key names and value types so ids, timestamps and tokens don't matter."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


@pytest.fixture(scope="module")
def creds():
    return {
        "email": f"parity-{uuid.uuid4().hex[:8]}@example.com",
        "password": "pw123456",
        "first_name": "P",
        "last_name": "T",
    }


def test_user_registered_in_go_can_login_in_python(creds):
    assert httpx.post(f"{GO}/api/v1/register", json=creds).status_code == 201
    login = {"email": creds["email"], "password": creds["password"]}
    go_login = httpx.post(f"{GO}/api/v1/login", json=login)
    py_login = httpx.post(f"{PY}/api/v1/login", json=login)
    assert go_login.status_code == py_login.status_code == 200
    assert shape(go_login.json()) == shape(py_login.json())


def test_token_from_python_is_accepted_by_go(creds):
    login = {"email": creds["email"], "password": creds["password"]}
    token = httpx.post(f"{PY}/api/v1/login", json=login).json()["token"]["access"]
    r = httpx.post(f"{GO}/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == creds["email"]


@pytest.mark.parametrize("path", ["/api/v1/", "/api/v1/nope"])
def test_public_responses_have_same_shape(path):
    go, py = httpx.get(f"{GO}{path}"), httpx.get(f"{PY}{path}")
    assert go.status_code == py.status_code
    assert shape(go.json()) == shape(py.json())


@pytest.mark.parametrize("path", ["/api/v1/data/users/", "/api/v1/data/user-permissions/"])
def test_crud_list_shape_matches(creds, path):
    login = {"email": creds["email"], "password": creds["password"]}
    token = httpx.post(f"{PY}/api/v1/login", json=login).json()["token"]["access"]
    h = {"Authorization": f"Bearer {token}"}
    go, py = httpx.get(f"{GO}{path}", headers=h), httpx.get(f"{PY}{path}", headers=h)
    assert go.status_code == py.status_code == 200
    assert shape(go.json()) == shape(py.json())
