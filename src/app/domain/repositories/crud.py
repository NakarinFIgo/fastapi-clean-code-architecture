from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.crud import DataListResponse, DataResponse


class ICrudRepository(ABC):
    @abstractmethod
    def get_one_by_id(self, id: str) -> DataResponse: ...

    @abstractmethod
    def get_list(
        self, page: int, page_size: int, filter: dict[str, Any] | None
    ) -> DataListResponse: ...

    @abstractmethod
    def describe(self, schema: str) -> dict[str, Any]: ...
