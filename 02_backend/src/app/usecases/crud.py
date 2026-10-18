from typing import Any

from app.domain.entities.crud import DataListResponse, DataResponse
from app.interface.repositories.crud_factory import CrudRepositoryFactory


class CrudUsecase:
    def __init__(self, factory: CrudRepositoryFactory) -> None:
        self._factory = factory

    def retrieve(self, slug: str, id: str) -> DataResponse:
        return self._factory.get(slug).get_one_by_id(id)

    def retrieve_list(self, slug: str, page: int, page_size: int) -> DataListResponse:
        # Go's handler parses query filters but passes nil to the usecase; same here.
        return self._factory.get(slug).get_list(page, page_size, None)

    def describe(self, slug: str, schema: str = "") -> dict[str, Any]:
        return self._factory.get(slug).describe(schema)
