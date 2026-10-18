from fastapi import APIRouter, Depends

from app.domain.entities.user import (
    UserEntity,
    UserLoginRequest,
    UserLoginResponse,
    UserRefreshTokenRequest,
    UserRegisterRequest,
)
from app.domain.errors import DomainError, ValidationError
from app.infrastructure.api.deps import get_user_usecase, require_user
from app.infrastructure.api.errors import ApiError
from app.usecases.user import UserUsecase

REGISTER_ERROR = "users-001"
LOGIN_ERROR = "users-002"
REFRESH_ERROR = "users-003"
LOGOUT_ERROR = "users-004"


def build_user_router() -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201, response_model=UserEntity)
    def register(
        req: UserRegisterRequest, usecase: UserUsecase = Depends(get_user_usecase)
    ) -> UserEntity:
        try:
            return usecase.register(req)
        except ValidationError as exc:
            raise ApiError(400, REGISTER_ERROR, str(exc)) from exc
        except DomainError as exc:
            # Parity with Go: duplicate email / hashing failure surface as HTTP 500.
            raise ApiError(500, REGISTER_ERROR, str(exc)) from exc

    @router.post("/login", response_model=UserLoginResponse)
    def login(
        req: UserLoginRequest, usecase: UserUsecase = Depends(get_user_usecase)
    ) -> UserLoginResponse:
        try:
            return usecase.login(req)
        except DomainError as exc:
            raise ApiError(400, LOGIN_ERROR, str(exc)) from exc

    @router.post("/logout")
    def logout(
        req: UserRefreshTokenRequest, usecase: UserUsecase = Depends(get_user_usecase)
    ) -> None:
        try:
            usecase.logout(req)
        except DomainError as exc:
            raise ApiError(400, LOGOUT_ERROR, str(exc)) from exc

    @router.post("/refresh-token", response_model=UserLoginResponse)
    def refresh_token(
        req: UserRefreshTokenRequest, usecase: UserUsecase = Depends(get_user_usecase)
    ) -> UserLoginResponse:
        try:
            return usecase.refresh(req)
        except DomainError as exc:
            raise ApiError(400, REFRESH_ERROR, str(exc)) from exc

    @router.post("/profile", response_model=UserEntity)
    def profile(user: UserEntity = Depends(require_user)) -> UserEntity:
        return user

    return router
