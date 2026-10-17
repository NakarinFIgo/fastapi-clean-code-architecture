from typing import Any

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.inspection import inspect

from app.domain.entities.crud import CrudResource
from app.shared.slug import to_crud_slug

_PY_TYPES: dict[Any, str] = {int: "int", bool: "boolean", str: "string", dict: "map"}


def _sa_type(column_type: Any) -> str:
    if isinstance(column_type, Boolean):
        return "boolean"
    if isinstance(column_type, Integer):
        return "int"
    if isinstance(column_type, DateTime):
        return "datetime"
    return "string"


def describe_resource(resource: CrudResource) -> dict[str, Any]:
    """Avro-like record description, same shape as Go's GenerateAvroSchema."""
    fields: list[dict[str, str]] = []
    if hasattr(resource.model, "__table__"):
        columns: Any = inspect(resource.model).columns
        for column in columns:
            if column.key not in resource.hidden:
                fields.append({"name": column.key, "type": _sa_type(column.type)})
    else:  # pydantic document model (Mongo)
        for name, info in resource.model.model_fields.items():  # type: ignore[attr-defined]
            if name not in resource.hidden:
                fields.append({"name": name, "type": _PY_TYPES.get(info.annotation, "string")})
    return {"type": "record", "name": to_crud_slug(resource.model.__name__), "fields": fields}
