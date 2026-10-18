import pytest

from app.domain.models.user import UserPermissionModel

CREDS = {
    "email": "ann@example.com",
    "password": "pw123456",
    "first_name": "Ann",
    "last_name": "Lee",
}


@pytest.fixture
def h(client):
    client.post("/api/v1/register", json=CREDS)
    r = client.post("/api/v1/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    return {"Authorization": f"Bearer {r.json()['token']['access']}"}


def test_requires_auth(client):
    assert client.get("/api/v1/data/users/").status_code == 401


def test_list_shape_and_no_password(client, h):
    r = client.get("/api/v1/data/users/", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "code",
        "data",
        "page",
        "page_size",
        "total_page",
        "total_data",
        "message",
        "data_schema",
    }
    assert body["page"] == 1 and body["page_size"] == 10
    assert body["data"][0]["email"] == CREDS["email"]
    assert "password" not in body["data"][0]


def test_list_totals_follow_go_rows_affected_semantics(client, session_factory, h):
    # Go computes total_data from RowsAffected, i.e. the rows on the current page.
    with session_factory() as s:
        for i in range(24):
            s.add(UserPermissionModel(user_id=None, permission=f"p{i}"))
        s.commit()
    body = client.get("/api/v1/data/user-permissions/?_page=2&_pageSize=10", headers=h).json()
    assert len(body["data"]) == 10
    assert body["page"] == 2
    assert body["total_data"] == 10
    assert body["total_page"] == 1


def test_user_permissions_use_go_json_keys(client, session_factory, h):
    with session_factory() as s:
        s.add(UserPermissionModel(user_id=1, permission="admin"))
        s.commit()
    row = client.get("/api/v1/data/user-permissions/", headers=h).json()["data"][0]
    assert row["ID"] == 1 and row["UserId"] == 1
    assert row["permission"] == "admin"
    assert "updated_at" in row


@pytest.mark.parametrize(
    "qs", ["_pageSize=-5", "_pageSize=0", "_pageSize=abc", "_page=0", "_page=abc"]
)
def test_list_bad_pagination_is_clamped(client, h, qs):
    r = client.get(f"/api/v1/data/users/?{qs}", headers=h)
    assert r.status_code == 200
    assert r.json()["page"] == 1
    assert r.json()["page_size"] == 10


def test_trailing_slash_optional(client, h):
    a = client.get("/api/v1/data/users", headers=h, follow_redirects=False)
    b = client.get("/api/v1/data/users/", headers=h, follow_redirects=False)
    assert a.status_code == 200 and b.status_code == 200


def test_get_one(client, h):
    uid = client.get("/api/v1/data/users/", headers=h).json()["data"][0]["id"]
    r = client.get(f"/api/v1/data/users/{uid}", headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["email"] == CREDS["email"]
    assert "password" not in r.json()["data"]
    assert r.json()["data_schema"]["type"] == "record"


def test_get_one_missing_or_bad_id_is_400_error_trace(client, h):
    for path in ("/api/v1/data/users/9999", "/api/v1/data/users/abc"):
        r = client.get(path, headers=h)
        assert r.status_code == 400
        assert r.json()["trace_id"] == "error"


def test_unknown_slug_400(client, h):
    r = client.get("/api/v1/data/nope/", headers=h)
    assert r.status_code == 400
    assert r.json() == {"trace_id": "error", "message": "Entity model not found"}


def test_user_tokens_not_exposed(client, h):
    assert client.get("/api/v1/data/user-tokens/", headers=h).status_code == 400


def test_describe_route_not_shadowed_by_id_route(client, h):
    r = client.get("/api/v1/data/users/describe", headers=h)
    assert r.status_code == 200
    assert r.json()["type"] == "record"
