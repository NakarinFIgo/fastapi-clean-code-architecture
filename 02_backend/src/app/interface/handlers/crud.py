from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.domain.entities.crud import DataListResponse, DataResponse
from app.domain.errors import DomainError
from app.infrastructure.api.deps import get_crud_usecase, require_user
from app.infrastructure.api.errors import ApiError
from app.usecases.crud import CrudUsecase

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 1000


def _positive_int(raw: str | None, default: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        return default
    return value if value >= 1 else default


def parse_pagination(query: Mapping[str, str]) -> tuple[int, int]:
    page = _positive_int(query.get("_page"), DEFAULT_PAGE)
    page_size = min(_positive_int(query.get("_pageSize"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    return page, page_size


def build_crud_router() -> APIRouter:
    router = APIRouter(
        prefix="/data",
        tags=["CRUD"],
        dependencies=[Depends(require_user)],
        include_in_schema=False,  # hidden from /docs; the endpoints still work
    )

    # describe must be registered before /{slug}/{id}
    @router.get("/{slug}/describe")
    def describe(slug: str, usecase: CrudUsecase = Depends(get_crud_usecase)) -> dict[str, Any]:
        try:
            return usecase.describe(slug)
        except DomainError as exc:
            raise ApiError(400, "error", str(exc)) from exc

    # Fiber treats /x and /x/ as the same route; register both so Starlette does not redirect.
    @router.get("/{slug}", response_model=DataListResponse, include_in_schema=False)
    @router.get("/{slug}/", response_model=DataListResponse)
    def retrieve_list(
        slug: str, request: Request, usecase: CrudUsecase = Depends(get_crud_usecase)
    ) -> DataListResponse:
        page, page_size = parse_pagination(request.query_params)
        try:
            return usecase.retrieve_list(slug, page, page_size)
        except DomainError as exc:
            raise ApiError(400, "error", str(exc)) from exc

    @router.get("/{slug}/{id}", response_model=DataResponse)
    def retrieve(
        slug: str, id: str, usecase: CrudUsecase = Depends(get_crud_usecase)
    ) -> DataResponse:
        try:
            return usecase.retrieve(slug, id)
        except DomainError as exc:
            raise ApiError(400, "error", str(exc)) from exc

    return router
