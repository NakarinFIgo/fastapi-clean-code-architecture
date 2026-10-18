from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.entities.user import UserEntity
from app.domain.errors import AuthError
from app.infrastructure.api.errors import ApiError
from app.infrastructure.api.registry import CRUD_RESOURCES
from app.interface.repositories.crud_factory import CrudRepositoryFactory
from app.interface.repositories.postgres_user import PostgresUserRepository
from app.shared.security import TokenService
from app.usecases.crud import CrudUsecase
from app.usecases.user import UserUsecase


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_user_usecase(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> UserUsecase:
    return UserUsecase(PostgresUserRepository(session), TokenService(settings))


def require_user(request: Request, usecase: UserUsecase = Depends(get_user_usecase)) -> UserEntity:
    # Read the raw header: a FastAPI Header(...) would answer 422 instead of our 401 envelope.
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        user, permission = usecase.authenticate(token)
    except AuthError as exc:
        raise ApiError(401, "middlware-002", str(exc)) from exc
    request.state.user_permission = permission
    return user


def get_crud_usecase(request: Request, session: Session = Depends(get_session)) -> CrudUsecase:
    return CrudUsecase(CrudRepositoryFactory(CRUD_RESOURCES, session, request.app.state.mongo_db))
