import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.crud import CrudResource, DataListResponse, DataResponse
from app.domain.errors import NotFoundError, ValidationError
from app.domain.repositories.crud import ICrudRepository
from app.shared.schema import describe_resource


class PostgresCrudRepository(ICrudRepository):
    def __init__(self, resource: CrudResource, session: Session) -> None:
        self._r = resource
        self._s = session

    def _serialize(self, row: Any) -> dict[str, Any]:
        return {
            self._r.aliases.get(c.key, c.key): getattr(row, c.key)
            for c in row.__table__.columns
            if c.key not in self._r.hidden
        }

    def get_one_by_id(self, id: str) -> DataResponse:
        try:
            pk = int(id)
        except ValueError as exc:
            raise ValidationError("invalid id") from exc
        row = self._s.get(self._r.model, pk)
        if row is None:
            raise NotFoundError("record not found")
        return DataResponse(data=self._serialize(row), data_schema=self.describe("detail"))

    def get_list(
        self, page: int, page_size: int, filter: dict[str, Any] | None
    ) -> DataListResponse:
        model: Any = self._r.model
        rows = self._s.scalars(
            select(model).order_by(model.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        # Parity with Go: totals come from GORM's RowsAffected, i.e. rows on THIS page.
        return DataListResponse(
            data=[self._serialize(r) for r in rows],
            page=page,
            page_size=page_size,
            total_page=math.ceil(len(rows) / page_size),
            total_data=len(rows),
            data_schema=self.describe("list"),
        )

    def describe(self, schema: str) -> dict[str, Any]:
        return describe_resource(self._r)
