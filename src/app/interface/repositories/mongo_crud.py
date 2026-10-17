import math
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.domain.entities.crud import CrudResource, DataListResponse, DataResponse
from app.domain.errors import NotFoundError, ValidationError
from app.domain.repositories.crud import ICrudRepository
from app.shared.schema import describe_resource


class MongoCrudRepository(ICrudRepository):
    def __init__(self, resource: CrudResource, collection: Collection) -> None:  # type: ignore[type-arg]
        self._r = resource
        self._c = collection

    def _serialize(self, doc: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in doc.items() if k != "_id" and k not in self._r.hidden}
        out["id"] = str(doc["_id"])
        return out

    def get_one_by_id(self, id: str) -> DataResponse:
        try:
            oid = ObjectId(id)
        except (InvalidId, TypeError) as exc:
            raise ValidationError("invalid id") from exc
        doc = self._c.find_one({"_id": oid})
        if doc is None:
            raise NotFoundError("record not found")
        return DataResponse(data=self._serialize(doc), data_schema=self.describe("detail"))

    def get_list(
        self, page: int, page_size: int, filter: dict[str, Any] | None
    ) -> DataListResponse:
        query = filter or {}
        total = self._c.count_documents(query)
        docs = self._c.find(query).sort("_id", 1).skip((page - 1) * page_size).limit(page_size)
        # Like Go's Mongo repo: real CountDocuments total, data_schema left empty.
        return DataListResponse(
            data=[self._serialize(d) for d in docs],
            page=page,
            page_size=page_size,
            total_page=math.ceil(total / page_size),
            total_data=total,
            data_schema=None,
        )

    def describe(self, schema: str) -> dict[str, Any]:
        return describe_resource(self._r)
