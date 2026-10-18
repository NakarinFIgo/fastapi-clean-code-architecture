import time

import pytest

from app.domain.entities.user import (
    UserLoginRequest,
    UserRefreshTokenRequest,
    UserRegisterRequest,
)
from app.domain.errors import (
    AuthError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from app.interface.repositories.postgres_user import PostgresUserRepository
from app.shared.security import TokenService
from app.usecases.user import UserUsecase


@pytest.fixture
def tokens(settings):
    return TokenService(settings)


@pytest.fixture
def usecase(session, tokens):
    return UserUsecase(PostgresUserRepository(session), tokens)


def register(usecase, email="ann@example.com", password="pw123456"):
    return usecase.register(UserRegisterRequest(email=email, password=password, first_name="Ann"))


def login(usecase):
    return usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))


def test_register_returns_entity_without_password(usecase):
    user = register(usecase)
    assert user.email == "ann@example.com"
    assert not hasattr(user, "password")


@pytest.mark.parametrize("email", ["nope", "a@b", "a@b.museum", "@b.co", "a b@c.co"])
def test_register_rejects_bad_email(usecase, email):
    with pytest.raises(ValidationError, match="email pattern is invalid"):
        register(usecase, email=email)


@pytest.mark.parametrize("password", ["x" * 73, "ก" * 25])  # 25 Thai chars = 75 bytes
def test_register_password_over_72_bytes_is_a_clean_error(usecase, password):
    with pytest.raises(DomainError, match="72 bytes") as info:
        register(usecase, password=password)
    assert not isinstance(info.value, ValidationError)  # Go answers 500 here, not 400


def test_register_duplicate_email(usecase):
    register(usecase)
    with pytest.raises(ConflictError):
        register(usecase)


def test_login_success_stores_tokens(usecase, tokens):
    user = register(usecase)
    res = login(usecase)
    assert res.user.id == user.id
    assert tokens.parse(res.token.access).user_id == user.id
    assert tokens.parse(res.token.refresh).user_id == user.id


def test_login_failures(usecase):
    register(usecase)
    with pytest.raises(NotFoundError, match="record not found"):
        usecase.login(UserLoginRequest(email="x@example.com", password="pw123456"))
    with pytest.raises(AuthError, match="password is invalid"):
        usecase.login(UserLoginRequest(email="ann@example.com", password="bad"))


def test_second_login_revokes_first_access_token(usecase):
    register(usecase)
    first = login(usecase)
    time.sleep(1.1)  # iat has 1s resolution; tokens must differ
    second = login(usecase)
    with pytest.raises(AuthError, match="user token not found"):
        usecase.authenticate(first.token.access)
    user, _ = usecase.authenticate(second.token.access)
    assert user.email == "ann@example.com"


def test_authenticate_returns_none_permission_when_missing(usecase):
    register(usecase)
    _, permission = usecase.authenticate(login(usecase).token.access)
    assert permission is None


def test_authenticate_bad_token(usecase):
    with pytest.raises(AuthError, match="token format is invalid"):
        usecase.authenticate("")


def test_refresh_keeps_refresh_expiry_and_rotates_access(usecase, tokens):
    register(usecase)
    first = login(usecase)
    old_exp = tokens.parse(first.token.refresh).expires_at
    time.sleep(1.1)
    res = usecase.refresh(UserRefreshTokenRequest(refresh_token=first.token.refresh))
    assert tokens.parse(res.token.refresh).expires_at == old_exp
    assert res.token.access != first.token.access
    usecase.authenticate(res.token.access)


def test_refresh_rejects_access_token_as_refresh(usecase):
    register(usecase)
    first = login(usecase)
    with pytest.raises(AuthError, match="user token not found"):
        usecase.refresh(UserRefreshTokenRequest(refresh_token=first.token.access))


def test_logout_deletes_tokens(usecase):
    register(usecase)
    first = login(usecase)
    usecase.logout(UserRefreshTokenRequest(refresh_token=first.token.refresh))
    with pytest.raises(AuthError, match="user token not found"):
        usecase.authenticate(first.token.access)
    with pytest.raises(AuthError, match="user token not found"):
        usecase.logout(UserRefreshTokenRequest(refresh_token=first.token.refresh))
