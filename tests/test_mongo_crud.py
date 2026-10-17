import mongomock
import pytest
from bson import ObjectId
from pydantic import BaseModel

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.errors import NotFoundError, ValidationError
from app.interface.repositories.crud_factory import CrudRepositoryFactory
from app.interface.repositories.mongo_crud import MongoCrudRepository


class ProductDoc(BaseModel):
    name: str
    price: int


RESOURCE = CrudResource("products", Datasource.MONGODB, ProductDoc)


@pytest.fixture
def collection():
    col = mongomock.MongoClient().db["products"]
    col.insert_many([{"name": f"p{i}", "price": i} for i in range(25)])
    return col


def test_get_one_renames_id(collection):
    oid = str(collection.find_one({"name": "p3"})["_id"])
    res = MongoCrudRepository(RESOURCE, collection).get_one_by_id(oid)
    assert res.data["id"] == oid
    assert "_id" not in res.data
    assert res.data["name"] == "p3"


def test_get_one_bad_or_missing_id(collection):
    repo = MongoCrudRepository(RESOURCE, collection)
    with pytest.raises(ValidationError):
        repo.get_one_by_id("not-an-object-id")
    with pytest.raises(NotFoundError):
        repo.get_one_by_id(str(ObjectId()))


def test_get_list_paginates_with_real_totals(collection):
    res = MongoCrudRepository(RESOURCE, collection).get_list(3, 10, None)
    assert len(res.data) == 5
    assert res.total_data == 25
    assert res.total_page == 3
    assert res.page == 3


def test_describe_uses_pydantic_fields(collection):
    schema = MongoCrudRepository(RESOURCE, collection).describe("list")
    assert {f["name"]: f["type"] for f in schema["fields"]} == {"name": "string", "price": "int"}


def test_factory_routes_mongo_resources(collection, session):
    factory = CrudRepositoryFactory([RESOURCE], session, collection.database)
    assert isinstance(factory.get("products"), MongoCrudRepository)


def test_factory_mongo_not_configured(session):
    factory = CrudRepositoryFactory([RESOURCE], session, None)
    with pytest.raises(NotFoundError, match="Datasource not supported"):
        factory.get("products")
