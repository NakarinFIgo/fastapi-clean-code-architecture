import re

from app.domain.entities.user import (
    UserEntity,
    UserLoginRequest,
    UserLoginResponse,
    UserRefreshTokenRequest,
    UserRegisterRequest,
    UserTokenEntity,
)
from app.domain.errors import AuthError, DomainError, NotFoundError, ValidationError
from app.domain.models.user import UserModel, UserPermissionModel
from app.domain.repositories.user import IUserRepository
from app.shared.security import (
    TokenClaims,
    TokenError,
    TokenService,
    TokenType,
    hash_password,
    verify_password,
)

# Same pattern as Go's UserRegisterRequest.IsEmail (ASCII \w, 2-4 char TLD).
EMAIL_PATTERN = re.compile(r"^[\w\-.]+@([\w\-]+\.)+[\w\-]{2,4}$", re.ASCII)
BCRYPT_MAX_BYTES = 72


class UserUsecase:
    def __init__(self, repo: IUserRepository, tokens: TokenService) -> None:
        self._repo = repo
        self._tokens = tokens

    def register(self, req: UserRegisterRequest) -> UserEntity:
        if not EMAIL_PATTERN.match(req.email):
            raise ValidationError("email pattern is invalid")
        if len(req.password.encode()) > BCRYPT_MAX_BYTES:
            # Go surfaces bcrypt's error as a generic failure (HTTP 500), not a validation one.
            raise DomainError(
                "hashed password failed: bcrypt: password length exceeds 72 bytes"
            )
        user = self._repo.insert_user(
            req.email, hash_password(req.password), req.first_name, req.last_name
        )
        return UserEntity.model_validate(user)

    def login(self, req: UserLoginRequest) -> UserLoginResponse:
        user = self._repo.get_by_email(req.email)
        if user is None:
            raise NotFoundError("record not found")
        if not verify_password(req.password, user.password):
            raise AuthError("password is invalid")
        return self._issue(user, refresh_expires_at=None)

    def refresh(self, req: UserRefreshTokenRequest) -> UserLoginResponse:
        claims = self._parse(req.refresh_token)
        row = self._repo.find_token_by_user(claims.user_id)
        if row is None or row.refresh != req.refresh_token or row.user is None:
            raise AuthError("user token not found")
        return self._issue(row.user, refresh_expires_at=claims.expires_at)

    def logout(self, req: UserRefreshTokenRequest) -> None:
        claims = self._parse(req.refresh_token)
        row = self._repo.find_token_by_user(claims.user_id)
        if row is None or row.refresh != req.refresh_token:
            raise AuthError("user token not found")
        self._repo.delete_token(claims.user_id)

    def authenticate(self, access_token: str) -> tuple[UserEntity, UserPermissionModel | None]:
        claims = self._parse(access_token)
        row = self._repo.find_token_by_user_and_access(claims.user_id, access_token)
        if row is None or row.user is None:
            raise AuthError("user token not found")
        permission = self._repo.get_permission(claims.user_id)
        return UserEntity.model_validate(row.user), permission

    def _parse(self, token: str) -> TokenClaims:
        try:
            return self._tokens.parse(token)
        except TokenError as exc:
            raise AuthError(str(exc)) from exc

    def _issue(self, user: UserModel, refresh_expires_at: int | None) -> UserLoginResponse:
        access = self._tokens.sign(TokenType.ACCESS, user.id)
        refresh = self._tokens.sign(TokenType.REFRESH, user.id, expires_at=refresh_expires_at)
        self._repo.upsert_token(user.id, access, refresh)
        return UserLoginResponse(
            user=UserEntity.model_validate(user),
            token=UserTokenEntity(access=access, refresh=refresh),
        )
