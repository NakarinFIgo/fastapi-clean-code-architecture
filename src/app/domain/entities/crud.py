from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.shared.slug import to_crud_slug


class Datasource(str, Enum):
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"


@dataclass(frozen=True)
class CrudResource:
    name: str  # table or collection name
    datasource: Datasource
    model: type
    hidden: frozenset[str] = frozenset()
    # column key -> JSON key, for models whose Go struct has no json tag
    aliases: dict[str, str] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return to_crud_slug(self.name)


class DataResponse(BaseModel):
    code: int = 0
    data: Any
    message: str = ""
    data_schema: dict[str, Any] | None = None


class DataListResponse(BaseModel):
    code: int = 0
    data: list[Any]
    page: int
    page_size: int
    total_page: int
    total_data: int
    message: str = ""
    data_schema: dict[str, Any] | None = None
