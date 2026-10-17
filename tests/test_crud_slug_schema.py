import pytest

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.models.user import UserModel
from app.interface.handlers.crud import parse_pagination
from app.shared.schema import describe_resource
from app.shared.slug import to_crud_slug


@pytest.mark.parametrize(
    "name,slug",
    [("users", "users"), ("user_permissions", "user-permissions"), ("UserModel", "user-model")],
)
def test_slug(name, slug):
    assert to_crud_slug(name) == slug


def test_describe_hides_password_and_maps_types():
    res = CrudResource("users", Datasource.POSTGRESQL, UserModel, hidden=frozenset({"password"}))
    schema = describe_resource(res)
    assert schema["type"] == "record"
    assert schema["name"] == "user-model"
    fields = {f["name"]: f["type"] for f in schema["fields"]}
    assert fields["id"] == "int"
    assert fields["email"] == "string"
    assert fields["created_at"] == "datetime"
    assert "password" not in fields


@pytest.mark.parametrize(
    "query,expected",
    [
        ({}, (1, 10)),
        ({"_page": "3", "_pageSize": "25"}, (3, 25)),
        ({"_pageSize": "0"}, (1, 10)),
        ({"_pageSize": "-5"}, (1, 10)),
        ({"_pageSize": "99999"}, (1, 1000)),
        ({"_pageSize": "abc"}, (1, 10)),
        ({"_page": "0"}, (1, 10)),
        ({"_page": "-2"}, (1, 10)),
        ({"_page": "abc"}, (1, 10)),
    ],
)
def test_parse_pagination_clamps(query, expected):
    assert parse_pagination(query) == expected
