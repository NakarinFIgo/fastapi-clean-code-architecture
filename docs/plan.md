> **Status: implemented.** Decision after writing this plan: keep strict parity with Go. So deviations 1, 2 and 3
> below were NOT applied (refresh uses ACCESS_EXPIRES, duplicate email and >72-byte password return 500, Postgres
> list totals count rows on the page). Deviations 4 and 5 were kept, plus `_pageSize < 1` falls back to 10.
> See README "Known differences from the Go project" for the final list.

# Python (FastAPI) Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/FastAPI service in `` that is wire-compatible with the existing Go API (same routes, JSON shapes, JWT tokens, Postgres tables), so the two can run side by side and traffic can move over route by route.

**Architecture:** Same Clean Architecture layers as the Go code (`domain` → `usecases` → `interface` → `infrastructure`), dependencies point inward only. Sync SQLAlchemy 2 + sync FastAPI handlers (matches Go's blocking style; async is a later decision). Dependencies are passed by constructor and wired in one composition root (`infrastructure/api/deps.py`), no module-level globals.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (psycopg3), PyMongo, pydantic-settings, PyJWT, bcrypt, pytest, httpx, mongomock, ruff, mypy.

**Spec:** none written. Derived from reading the Go source in `src/` (commit `be30c67`). The Global Constraints below are the contract extracted from it.

## Global Constraints

- Python `>=3.12`; Go code under `src/` is **not modified** by this plan. All new code lives in ``.
- All routes sit under the `/api/v1` prefix (Go: `s.app.Group("/api/v1")`). Swagger UI is at `/swagger/*` (root, not under `/api/v1`) in Go; Python serves FastAPI docs at `/docs` instead (intentional).
- Success responses are the **bare payload**, no envelope. Error responses are exactly `{"trace_id": "<code>", "message": "<text>"}`.
- Trace ids to keep verbatim: `users-001` register, `users-002` login, `users-003` refresh (also logout body-parse errors), `users-004` logout, `middlware-001` route not found (message `rotuer not found`), `middlware-002` JWT auth (sic, misspelled), `error` for CRUD.
- Env var names stay `GOAPP_*` (see `env.template`). `GOAPP_SECRET_KEY` has **no default**.
- JWT: HS256, secret `GOAPP_SECRET_KEY`, payload `{"claims": {"id": <int>}, "iss", "sub", "aud": ["user","admin"], "exp", "nbf", "iat"}`. `sub` is `access-token` or `refresh-token`. `iss` is `GOAPP_NAME.lower()` with spaces kept (Go discards the result of `strings.Replace`). `aud` is **not** validated on decode.
- Passwords: bcrypt cost 10; Go-issued hashes (`$2a$`) must verify.
- DB tables shared with Go: `users(id, email unique, first_name, last_name, created_at, updated_at, password)`, `user_tokens(id, user_id idx fk users.id, access, refresh, updated_at)`, `user_permissions(id, user_id idx fk users.id, permission, updated_at)`. One `user_tokens` row per user; an access token is only valid if it equals the stored one (new login revokes old tokens, logout deletes the row).
- CRUD slug = table name, snake→kebab (`user_permissions` → `user-permissions`). List query params `_page` (default 1) and `_pageSize` (default 10, max 1000); other query params are ignored (Go passes `nil` filter).
- Routes: `GET /api/v1/`; `POST /api/v1/users/{register,login,logout,refresh-token,profile}`; `GET /api/v1/data/{slug}/describe`, `GET /api/v1/data/{slug}/`, `GET /api/v1/data/{slug}/{id}`. Register returns 201, everything else 200. Unknown route → 404.
- CORS: allow all origins, methods `GET,POST,HEAD,PUT,DELETE,PATCH`.

**Intentional deviations from Go (need owner sign-off before Task 5/6):**
1. Refresh token lifetime uses `GOAPP_JWT_REFRESH_EXPIRES` (Go wrongly uses `ACCESS_EXPIRES`).
2. Duplicate email on register → `409` (Go: `500`).
3. List `total_data`/`total_page` are real counts (Go uses rows-on-this-page).
4. `user_tokens` is **not** exposed through `/data/...` (Go exposes access/refresh tokens of every user to any logged-in user).
5. A user with no `user_permissions` row is allowed through (Go would panic on a nil type assertion in the CRUD handlers).

## Review Focus

- JWT that carries an `aud` claim must still decode (PyJWT rejects it by default) → Task 2.
- Password longer than 72 bytes must give `400`, not a 500/traceback (bcrypt limit) → Task 4.
- `_pageSize=-5`, `_pageSize=0`, `_pageSize=abc`, `_page=0` must clamp/default, never return unbounded rows → Task 6.
- `/data/users` and `/data/users/` must both work (Fiber ignores trailing slash; Starlette redirects) → Task 6.
- `Authorization` missing, `Bearer` with no token, or lowercase `bearer x` must give 401 in the error envelope, not 422/500 → Task 5.

---

## File Structure

```

  pyproject.toml
  Dockerfile
  src/app/
    config.py                              Settings (pydantic-settings)
    domain/
      errors.py                            DomainError, NotFoundError, ConflictError, ValidationError
      entities/user.py                     UserEntity, UserTokenEntity, UserLoginResponse, UserRegisterRequest, ...
      entities/crud.py                     DataResponse, DataListResponse, CrudResource, Datasource
      models/user.py                       SQLAlchemy Base, UserModel, UserTokenModel, UserPermissionModel
      repositories/user.py                 IUserRepository (ABC)
      repositories/crud.py                 ICrudRepository (ABC)
    shared/
      security.py                          hash_password, verify_password, TokenService
      slug.py                              to_crud_slug
      schema.py                            describe_resource
    usecases/
      user.py                              UserUsecase
      crud.py                              CrudUsecase
    interface/
      repositories/postgres_user.py        PostgresUserRepository
      repositories/postgres_crud.py        PostgresCrudRepository
      repositories/mongo_crud.py           MongoCrudRepository
      repositories/crud_factory.py         CrudRepositoryFactory
      handlers/monitor.py, user.py, crud.py
    infrastructure/
      db/postgres.py                       engine/session factory
      db/mongo.py                          Mongo client factory
      db/migrate.py                        create tables
      api/main.py                          create_app()
      api/deps.py                          composition root
      api/errors.py                        ApiError + exception handlers
      api/registry.py                      CRUD_RESOURCES
  tests/
    conftest.py, test_config.py, test_security.py, test_user_repository.py,
    test_user_usecase.py, test_user_api.py, test_crud_*.py, contract/
```

---

### Task 1: Scaffold, config, health check, 404 envelope

**Files:**
- Create: `pyproject.toml`, `src/app/__init__.py` (empty), `src/app/config.py`
- Create: `src/app/infrastructure/__init__.py`, `.../infrastructure/api/__init__.py` (empty), `.../infrastructure/api/errors.py`, `.../infrastructure/api/main.py`
- Create: `src/app/interface/__init__.py`, `.../interface/handlers/__init__.py` (empty), `.../interface/handlers/monitor.py`
- Create: `tests/conftest.py`, `tests/test_config.py`, `tests/test_monitor_api.py`

**Interfaces:**
- Produces: `Settings` (fields below), `create_app(settings: Settings | None = None) -> FastAPI`, `ApiError(status_code: int, trace_id: str, message: str)`, `install_error_handlers(app: FastAPI) -> None`, `conftest.settings` fixture returning a test `Settings`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "clean-code-api"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "pymongo>=4.8",
  "pydantic-settings>=2.4",
  "pyjwt>=2.9",
  "bcrypt>=4.2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "mongomock>=4.2", "ruff>=0.6", "mypy>=1.11"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
markers = ["contract: needs live Go and Python servers"]
addopts = "-m 'not contract'"

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

- [ ] **Step 2: Install**

Run: `python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: installs without error.

- [ ] **Step 3: Write failing tests**

`tests/conftest.py`
```python
import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        goapp_name="GOLANG FIRST API APP",
        goapp_version="0.0.1",
        goapp_secret_key="test-secret-key-test-secret-key-12",
        goapp_jwt_access_expires=86400,
        goapp_jwt_refresh_expires=172800,
    )
```

`tests/test_config.py`
```python
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_postgres_url_escapes_password():
    s = Settings(
        _env_file=None,
        goapp_secret_key="k",
        goapp_postgres_db_user="u",
        goapp_postgres_db_password="p@ss/word",
        goapp_postgres_db_host="h",
        goapp_postgres_db_port=5433,
        goapp_postgres_db_name="d",
    )
    assert s.postgres_url == "postgresql+psycopg://u:p%40ss%2Fword@h:5433/d"


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("GOAPP_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

`tests/test_monitor_api.py`
```python
from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


def test_health_check(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/")
    assert r.status_code == 200
    assert r.json() == {"name": "GOLANG FIRST API APP", "version": "0.0.1"}


def test_unknown_route_uses_error_envelope(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json() == {"trace_id": "middlware-001", "message": "rotuer not found"}


def test_cors_allows_any_origin(settings):
    client = TestClient(create_app(settings))
    r = client.get("/api/v1/", headers={"Origin": "http://x.test"})
    assert r.headers["access-control-allow-origin"] == "*"
```

- [ ] **Step 4: Run to verify failure**

Run: `pytest -q`
Expected: collection errors, `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 5: Implement**

`src/app/config.py`
```python
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.dev"), extra="ignore")

    goapp_host: str = "127.0.0.1"
    goapp_port: int = 3000
    goapp_name: str = "GOLANG FIRST API APP"
    goapp_version: str = "0.0.1"

    goapp_postgres_db_name: str = "postgres"
    goapp_postgres_db_user: str = "postgres"
    goapp_postgres_db_password: str = ""
    goapp_postgres_db_host: str = "localhost"
    goapp_postgres_db_port: int = 5432

    goapp_mongodb_db_atlas_uri: str = ""
    goapp_mongodb_db_name: str = ""

    goapp_secret_key: str
    goapp_jwt_access_expires: int = 86400
    goapp_jwt_refresh_expires: int = 172800

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg://{quote_plus(self.goapp_postgres_db_user)}"
            f":{quote_plus(self.goapp_postgres_db_password)}"
            f"@{self.goapp_postgres_db_host}:{self.goapp_postgres_db_port}"
            f"/{self.goapp_postgres_db_name}"
        )
```

`src/app/infrastructure/api/errors.py`
```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

VALIDATION_TRACE_IDS = {
    "/api/v1/users/register": "users-001",
    "/api/v1/users/login": "users-002",
    "/api/v1/users/refresh-token": "users-003",
    "/api/v1/users/logout": "users-003",
}


class ApiError(Exception):
    def __init__(self, status_code: int, trace_id: str, message: str) -> None:
        self.status_code = status_code
        self.trace_id = trace_id
        self.message = message


def error_response(status_code: int, trace_id: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"trace_id": trace_id, "message": message})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.trace_id, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "middlware-001", "rotuer not found")
        return error_response(exc.status_code, "error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = VALIDATION_TRACE_IDS.get(request.url.path, "error")
        first = exc.errors()[0] if exc.errors() else {}
        return error_response(400, trace_id, str(first.get("msg", "invalid request")))
```

`src/app/interface/handlers/monitor.py`
```python
from fastapi import APIRouter

from app.config import Settings


def build_monitor_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["Monitor"])

    @router.get("/")
    def health_check() -> dict[str, str]:
        return {"name": settings.goapp_name, "version": settings.goapp_version}

    return router
```

`src/app/infrastructure/api/main.py`
```python
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.infrastructure.api.errors import install_error_handlers
from app.interface.handlers.monitor import build_monitor_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    app = FastAPI(title=settings.goapp_name, version=settings.goapp_version)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "HEAD", "PUT", "DELETE", "PATCH"],
        allow_headers=[],
        allow_credentials=False,
    )
    install_error_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(build_monitor_router(settings))
    app.include_router(api_v1)
    return app
```

- [ ] **Step 6: Run to verify pass**

Run: `pytest -q`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add 
git commit -m "feat(python): scaffold FastAPI app with config, health check and error envelope"
```

---

### Task 2: Security primitives (bcrypt + JWT)

**Files:**
- Create: `src/app/shared/__init__.py` (empty), `src/app/shared/security.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `Settings` (Task 1).
- Produces:
  - `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`
  - `class TokenType(str, Enum)`: `ACCESS = "access"`, `REFRESH = "refresh"`
  - `class TokenError(Exception)` (message is the user-facing text)
  - `@dataclass(frozen=True) class TokenClaims: user_id: int; expires_at: int`
  - `class TokenService(settings: Settings)` with `.sign(token_type: TokenType, user_id: int, expires_at: int | None = None) -> str` and `.parse(token: str) -> TokenClaims`

- [ ] **Step 1: Write failing tests**

`tests/test_security.py`
```python
import time

import jwt
import pytest

from app.shared.security import (
    TokenError,
    TokenService,
    TokenType,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed.startswith("$2")
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_verifies_hash_made_by_go_bcrypt():
    # Real "$2a$" cost-10 hash (the prefix Go's bcrypt emits) of "s3cret".
    go_hash = "$2a$10$kWxvjgYFmpRMMxky1P6IL./zmczCfmg93K57sPFVGGlmNmGcxnV6u"
    assert verify_password("s3cret", go_hash)
    assert not verify_password("wrong", go_hash)


def test_verify_password_with_garbage_hash_is_false():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_payload_matches_go_shape(settings):
    svc = TokenService(settings)
    token = svc.sign(TokenType.ACCESS, 7)
    payload = jwt.decode(
        token, settings.goapp_secret_key, algorithms=["HS256"], options={"verify_aud": False}
    )
    assert payload["claims"] == {"id": 7}
    assert payload["sub"] == "access-token"
    assert payload["aud"] == ["user", "admin"]
    assert payload["iss"] == "golang first api app"
    assert payload["exp"] - payload["iat"] == settings.goapp_jwt_access_expires
    assert payload["nbf"] == payload["iat"]


def test_refresh_token_uses_refresh_lifetime(settings):
    svc = TokenService(settings)
    token = svc.sign(TokenType.REFRESH, 7)
    payload = jwt.decode(
        token, settings.goapp_secret_key, algorithms=["HS256"], options={"verify_aud": False}
    )
    assert payload["sub"] == "refresh-token"
    assert payload["exp"] - payload["iat"] == settings.goapp_jwt_refresh_expires


def test_parse_accepts_token_with_aud_claim(settings):
    # Review focus: PyJWT rejects tokens with `aud` unless told not to verify it.
    svc = TokenService(settings)
    claims = svc.parse(svc.sign(TokenType.ACCESS, 42))
    assert claims.user_id == 42


def test_sign_with_fixed_expiry_is_kept(settings):
    svc = TokenService(settings)
    exp = int(time.time()) + 1000
    assert svc.parse(svc.sign(TokenType.REFRESH, 1, expires_at=exp)).expires_at == exp


def test_parse_errors_use_go_messages(settings):
    svc = TokenService(settings)
    with pytest.raises(TokenError, match="token format is invalid"):
        svc.parse("")
    with pytest.raises(TokenError, match="token format is invalid"):
        svc.parse("abc")
    expired = jwt.encode(
        {"claims": {"id": 1}, "exp": int(time.time()) - 10}, settings.goapp_secret_key, "HS256"
    )
    with pytest.raises(TokenError, match="token had expired"):
        svc.parse(expired)
    forged = jwt.encode({"claims": {"id": 1}}, "other-secret-other-secret-other-secret", "HS256")
    with pytest.raises(TokenError, match="parse token failed"):
        svc.parse(forged)


def test_parse_rejects_token_without_claims(settings):
    svc = TokenService(settings)
    token = jwt.encode({"exp": int(time.time()) + 100}, settings.goapp_secret_key, "HS256")
    with pytest.raises(TokenError, match="claims type is invalid"):
        svc.parse(token)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_security.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.shared'`.

- [ ] **Step 3: Implement**

`src/app/shared/security.py`
```python
import time
from dataclasses import dataclass
from enum import Enum

import bcrypt
import jwt

from app.config import Settings

BCRYPT_COST = 10


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    expires_at: int


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.goapp_secret_key
        self._issuer = settings.goapp_name.lower()
        self._lifetimes = {
            TokenType.ACCESS: settings.goapp_jwt_access_expires,
            TokenType.REFRESH: settings.goapp_jwt_refresh_expires,
        }

    def sign(self, token_type: TokenType, user_id: int, expires_at: int | None = None) -> str:
        now = int(time.time())
        payload = {
            "claims": {"id": user_id},
            "iss": self._issuer,
            "sub": f"{token_type.value}-token",
            "aud": ["user", "admin"],
            "exp": expires_at if expires_at is not None else now + self._lifetimes[token_type],
            "nbf": now,
            "iat": now,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def parse(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=["HS256"], options={"verify_aud": False}
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("token had expired") from exc
        except jwt.DecodeError as exc:
            if "signature" in str(exc).lower():
                raise TokenError(f"parse token failed: {exc}") from exc
            raise TokenError("token format is invalid") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"parse token failed: {exc}") from exc

        claims = payload.get("claims")
        if not isinstance(claims, dict) or not isinstance(claims.get("id"), int):
            raise TokenError("claims type is invalid")
        return TokenClaims(user_id=claims["id"], expires_at=int(payload["exp"]))
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_security.py -v`
Expected: all pass. If `test_parse_errors_use_go_messages` fails on the forged-signature case, print `str(exc)` from PyJWT (`Signature verification failed` raises `InvalidSignatureError`, a `DecodeError` subclass) and adjust the `"signature"` check; do not weaken the other assertions.

- [ ] **Step 5: Commit**

```bash
git add src/app/shared tests/test_security.py
git commit -m "feat(python): bcrypt and JWT primitives compatible with Go tokens"
```

---

### Task 3: Domain models, errors, user repository

**Files:**
- Create: `src/app/domain/__init__.py`, `.../domain/errors.py`, `.../domain/models/__init__.py`, `.../domain/models/user.py`, `.../domain/entities/__init__.py`, `.../domain/entities/user.py`, `.../domain/repositories/__init__.py`, `.../domain/repositories/user.py`
- Create: `src/app/interface/repositories/__init__.py`, `.../interface/repositories/postgres_user.py`
- Create: `src/app/infrastructure/db/__init__.py`, `.../infrastructure/db/postgres.py`, `.../infrastructure/db/migrate.py`
- Test: `tests/test_user_repository.py` (and extend `conftest.py`)

**Interfaces:**
- Consumes: `Settings`.
- Produces:
  - `errors.py`: `class DomainError(Exception)`; `ValidationError(DomainError)`, `NotFoundError(DomainError)`, `ConflictError(DomainError)`, `AuthError(DomainError)`.
  - `models/user.py`: `Base`, `UserModel(id, email, first_name, last_name, password, created_at, updated_at)`, `UserTokenModel(id, user_id, access, refresh, updated_at, user)`, `UserPermissionModel(id, user_id, permission, updated_at)`.
  - `entities/user.py` (pydantic): `UserEntity(id, email, first_name, last_name, created_at, updated_at)` with `from_attributes`; `UserTokenEntity(access, refresh)`; `UserLoginResponse(user, token)`; `UserRegisterRequest(email, password, first_name="", last_name="")`; `UserLoginRequest(email, password)`; `UserRefreshTokenRequest(refresh_token)`.
  - `IUserRepository` (ABC): `insert_user(email: str, password_hash: str, first_name: str, last_name: str) -> UserModel`; `get_by_email(email: str) -> UserModel | None`; `get_by_id(user_id: int) -> UserModel | None`; `upsert_token(user_id: int, access: str, refresh: str) -> None`; `find_token_by_user(user_id: int) -> UserTokenModel | None`; `find_token_by_user_and_access(user_id: int, access: str) -> UserTokenModel | None`; `delete_token(user_id: int) -> None`; `get_permission(user_id: int) -> UserPermissionModel | None`. `insert_user` raises `ConflictError("email already registered")` on duplicate email.
  - `postgres.py`: `build_session_factory(url: str) -> sessionmaker[Session]`.
  - `migrate.py`: `create_tables(engine: Engine) -> None`, runnable as `python -m app.infrastructure.db.migrate`.
  - `PostgresUserRepository(session: Session)`.

- [ ] **Step 1: Extend `conftest.py` with an in-memory DB fixture**

Append to `tests/conftest.py`:
```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.models.user import Base


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s
```

- [ ] **Step 2: Write failing tests**

`tests/test_user_repository.py`
```python
import pytest

from app.domain.errors import ConflictError
from app.domain.models.user import UserPermissionModel
from app.interface.repositories.postgres_user import PostgresUserRepository


@pytest.fixture
def repo(session):
    return PostgresUserRepository(session)


def make_user(repo, email="a@b.co"):
    return repo.insert_user(email, "hash", "Ann", "Lee")


def test_insert_and_get(repo):
    user = make_user(repo)
    assert user.id is not None
    assert user.created_at is not None
    assert repo.get_by_email("a@b.co").id == user.id
    assert repo.get_by_id(user.id).email == "a@b.co"
    assert repo.get_by_email("missing@b.co") is None


def test_duplicate_email_raises_conflict(repo):
    make_user(repo)
    with pytest.raises(ConflictError):
        make_user(repo)
    # session must still be usable after the failed insert
    assert make_user(repo, "other@b.co").id is not None


def test_upsert_token_keeps_one_row_per_user(repo):
    user = make_user(repo)
    repo.upsert_token(user.id, "a1", "r1")
    repo.upsert_token(user.id, "a2", "r2")
    row = repo.find_token_by_user(user.id)
    assert (row.access, row.refresh) == ("a2", "r2")
    assert repo.find_token_by_user_and_access(user.id, "a1") is None
    assert repo.find_token_by_user_and_access(user.id, "a2") is not None


def test_delete_token(repo):
    user = make_user(repo)
    repo.upsert_token(user.id, "a", "r")
    repo.delete_token(user.id)
    assert repo.find_token_by_user(user.id) is None


def test_get_permission(repo, session):
    user = make_user(repo)
    assert repo.get_permission(user.id) is None
    session.add(UserPermissionModel(user_id=user.id, permission="admin"))
    session.commit()
    assert repo.get_permission(user.id).permission == "admin"
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_user_repository.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.domain'`.

- [ ] **Step 4: Implement domain layer**

`src/app/domain/errors.py`
```python
class DomainError(Exception):
    """Base for errors the usecases raise; handlers map them to HTTP."""


class ValidationError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class AuthError(DomainError):
    pass
```

`src/app/domain/models/user.py`
```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    first_name: Mapped[str] = mapped_column(String, default="")
    last_name: Mapped[str] = mapped_column(String, default="")
    password: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class UserTokenModel(Base):
    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"), index=True
    )
    access: Mapped[str] = mapped_column(String, default="")
    refresh: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    user: Mapped[UserModel | None] = relationship()


class UserPermissionModel(Base):
    __tablename__ = "user_permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"), index=True
    )
    permission: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
```

`src/app/domain/entities/user.py`
```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


class UserTokenEntity(BaseModel):
    access: str
    refresh: str


class UserLoginResponse(BaseModel):
    user: UserEntity
    token: UserTokenEntity


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserRefreshTokenRequest(BaseModel):
    refresh_token: str
```

`src/app/domain/repositories/user.py`
```python
from abc import ABC, abstractmethod

from app.domain.models.user import UserModel, UserPermissionModel, UserTokenModel


class IUserRepository(ABC):
    @abstractmethod
    def insert_user(
        self, email: str, password_hash: str, first_name: str, last_name: str
    ) -> UserModel: ...

    @abstractmethod
    def get_by_email(self, email: str) -> UserModel | None: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> UserModel | None: ...

    @abstractmethod
    def upsert_token(self, user_id: int, access: str, refresh: str) -> None: ...

    @abstractmethod
    def find_token_by_user(self, user_id: int) -> UserTokenModel | None: ...

    @abstractmethod
    def find_token_by_user_and_access(self, user_id: int, access: str) -> UserTokenModel | None: ...

    @abstractmethod
    def delete_token(self, user_id: int) -> None: ...

    @abstractmethod
    def get_permission(self, user_id: int) -> UserPermissionModel | None: ...
```

- [ ] **Step 5: Implement repository, session factory, migration**

`src/app/interface/repositories/postgres_user.py`
```python
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.errors import ConflictError
from app.domain.models.user import UserModel, UserPermissionModel, UserTokenModel
from app.domain.repositories.user import IUserRepository


class PostgresUserRepository(IUserRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert_user(
        self, email: str, password_hash: str, first_name: str, last_name: str
    ) -> UserModel:
        user = UserModel(
            email=email, password=password_hash, first_name=first_name, last_name=last_name
        )
        self._s.add(user)
        try:
            self._s.commit()
        except IntegrityError as exc:
            self._s.rollback()
            raise ConflictError("email already registered") from exc
        return user

    def get_by_email(self, email: str) -> UserModel | None:
        return self._s.scalar(select(UserModel).where(UserModel.email == email))

    def get_by_id(self, user_id: int) -> UserModel | None:
        return self._s.get(UserModel, user_id)

    def upsert_token(self, user_id: int, access: str, refresh: str) -> None:
        row = self.find_token_by_user(user_id)
        if row is None:
            row = UserTokenModel(user_id=user_id)
            self._s.add(row)
        row.access = access
        row.refresh = refresh
        self._s.commit()

    def find_token_by_user(self, user_id: int) -> UserTokenModel | None:
        return self._s.scalar(select(UserTokenModel).where(UserTokenModel.user_id == user_id))

    def find_token_by_user_and_access(self, user_id: int, access: str) -> UserTokenModel | None:
        return self._s.scalar(
            select(UserTokenModel).where(
                UserTokenModel.user_id == user_id, UserTokenModel.access == access
            )
        )

    def delete_token(self, user_id: int) -> None:
        self._s.execute(delete(UserTokenModel).where(UserTokenModel.user_id == user_id))
        self._s.commit()

    def get_permission(self, user_id: int) -> UserPermissionModel | None:
        return self._s.scalar(
            select(UserPermissionModel).where(UserPermissionModel.user_id == user_id)
        )
```

`src/app/infrastructure/db/postgres.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_session_factory(url: str) -> sessionmaker[Session]:
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)
```

`src/app/infrastructure/db/migrate.py`
```python
from sqlalchemy import Engine, create_engine

from app.config import Settings
from app.domain.models.user import Base


def create_tables(engine: Engine) -> None:
    """create_all skips tables that already exist, so it is safe on a DB the Go app migrated."""
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    engine = create_engine(Settings().postgres_url)  # type: ignore[call-arg]
    create_tables(engine)
    print("Migration success !!!")
```

- [ ] **Step 6: Run to verify pass**

Run: `pytest tests/test_user_repository.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add 
git commit -m "feat(python): user models, repository and table creation"
```

---

### Task 4: User usecase

**Files:**
- Create: `src/app/usecases/__init__.py`, `src/app/usecases/user.py`
- Test: `tests/test_user_usecase.py`

**Interfaces:**
- Consumes: `IUserRepository`, `TokenService`, `TokenType`, `TokenError`, `hash_password`, `verify_password`, entities, errors.
- Produces: `class UserUsecase(repo: IUserRepository, tokens: TokenService)` with
  - `register(req: UserRegisterRequest) -> UserEntity`
  - `login(req: UserLoginRequest) -> UserLoginResponse`
  - `refresh(req: UserRefreshTokenRequest) -> UserLoginResponse`
  - `logout(req: UserRefreshTokenRequest) -> None`
  - `authenticate(access_token: str) -> tuple[UserEntity, UserPermissionModel | None]`
  - Errors: `ValidationError` (bad email, password >72 bytes), `ConflictError`, `NotFoundError` ("record not found"), `AuthError` (all token/password failures; message is the Go text).
  - Constant `EMAIL_PATTERN` = Go's `^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$`.

- [ ] **Step 1: Write failing tests**

`tests/test_user_usecase.py`
```python
import time

import pytest

from app.domain.entities.user import (
    UserLoginRequest,
    UserRefreshTokenRequest,
    UserRegisterRequest,
)
from app.domain.errors import AuthError, ConflictError, NotFoundError, ValidationError
from app.interface.repositories.postgres_user import PostgresUserRepository
from app.shared.security import TokenService, TokenType
from app.usecases.user import UserUsecase


@pytest.fixture
def tokens(settings):
    return TokenService(settings)


@pytest.fixture
def usecase(session, tokens):
    return UserUsecase(PostgresUserRepository(session), tokens)


def register(usecase, email="ann@example.com", password="pw123456"):
    return usecase.register(UserRegisterRequest(email=email, password=password, first_name="Ann"))


def test_register_returns_entity_without_password(usecase):
    user = register(usecase)
    assert user.email == "ann@example.com"
    assert not hasattr(user, "password")


@pytest.mark.parametrize("email", ["nope", "a@b", "a@b.museum", "@b.co", "a b@c.co"])
def test_register_rejects_bad_email(usecase, email):
    with pytest.raises(ValidationError, match="email pattern is invalid"):
        register(usecase, email=email)


def test_register_rejects_password_over_72_bytes(usecase):
    # Review focus: bcrypt limit must be a 400-class error, not a crash.
    with pytest.raises(ValidationError, match="72 bytes"):
        register(usecase, password="x" * 73)
    with pytest.raises(ValidationError, match="72 bytes"):
        register(usecase, password="ก" * 25)  # 75 bytes in UTF-8, 25 characters


def test_register_duplicate_email(usecase):
    register(usecase)
    with pytest.raises(ConflictError):
        register(usecase)


def test_login_success_stores_tokens(usecase, tokens):
    user = register(usecase)
    res = usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))
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
    req = UserLoginRequest(email="ann@example.com", password="pw123456")
    first = usecase.login(req)
    time.sleep(1.1)  # iat has 1s resolution; tokens must differ
    second = usecase.login(req)
    with pytest.raises(AuthError, match="user token not found"):
        usecase.authenticate(first.token.access)
    user, _ = usecase.authenticate(second.token.access)
    assert user.email == "ann@example.com"


def test_authenticate_returns_none_permission_when_missing(usecase):
    register(usecase)
    res = usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))
    _, permission = usecase.authenticate(res.token.access)
    assert permission is None


def test_authenticate_bad_token(usecase):
    with pytest.raises(AuthError, match="token format is invalid"):
        usecase.authenticate("")


def test_refresh_keeps_refresh_expiry_and_rotates_access(usecase, tokens):
    register(usecase)
    login = usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))
    old_exp = tokens.parse(login.token.refresh).expires_at
    time.sleep(1.1)
    res = usecase.refresh(UserRefreshTokenRequest(refresh_token=login.token.refresh))
    assert tokens.parse(res.token.refresh).expires_at == old_exp
    assert res.token.access != login.token.access
    usecase.authenticate(res.token.access)


def test_refresh_rejects_unknown_or_access_token(usecase):
    register(usecase)
    login = usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))
    with pytest.raises(AuthError, match="user token not found"):
        usecase.refresh(UserRefreshTokenRequest(refresh_token=login.token.access))


def test_logout_deletes_tokens(usecase):
    register(usecase)
    login = usecase.login(UserLoginRequest(email="ann@example.com", password="pw123456"))
    usecase.logout(UserRefreshTokenRequest(refresh_token=login.token.refresh))
    with pytest.raises(AuthError, match="user token not found"):
        usecase.authenticate(login.token.access)
    with pytest.raises(AuthError, match="user token not found"):
        usecase.logout(UserRefreshTokenRequest(refresh_token=login.token.refresh))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_user_usecase.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.usecases'`.

- [ ] **Step 3: Implement**

`src/app/usecases/user.py`
```python
import re

from app.domain.entities.user import (
    UserEntity,
    UserLoginRequest,
    UserLoginResponse,
    UserRefreshTokenRequest,
    UserRegisterRequest,
    UserTokenEntity,
)
from app.domain.errors import AuthError, NotFoundError, ValidationError
from app.domain.models.user import UserModel, UserPermissionModel
from app.domain.repositories.user import IUserRepository
from app.shared.security import (
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
            raise ValidationError("password must be at most 72 bytes")
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

    def _parse(self, token: str):  # type: ignore[no-untyped-def]
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_user_usecase.py -v`
Expected: all pass (two tests sleep ~1s each).

- [ ] **Step 5: Commit**

```bash
git add src/app/usecases tests/test_user_usecase.py
git commit -m "feat(python): user usecase (register, login, refresh, logout, authenticate)"
```

---

### Task 5: User HTTP handlers + JWT dependency + composition root

**Files:**
- Create: `src/app/infrastructure/api/deps.py`, `src/app/interface/handlers/user.py`
- Modify: `src/app/infrastructure/api/main.py`
- Test: `tests/test_user_api.py`; extend `conftest.py` with `client` fixture

**Interfaces:**
- Consumes: `UserUsecase`, `PostgresUserRepository`, `ApiError`, `Settings`.
- Produces:
  - `deps.py`: `get_settings(request) -> Settings`; `get_session(request) -> Iterator[Session]` (uses `request.app.state.session_factory`); `get_user_usecase(...) -> UserUsecase`; `require_user(...) -> UserEntity` (JWT auth; raises `ApiError(401, "middlware-002", msg)`; also stores permission on `request.state.user_permission`).
  - `create_app(settings=None, session_factory=None)` — `session_factory` param lets tests inject SQLite; default builds Postgres factory from settings.
  - `build_user_router() -> APIRouter` mounted at `/users`.

- [ ] **Step 1: Add `client` fixture**

Append to `tests/conftest.py`:
```python
from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


@pytest.fixture
def client(settings, session_factory) -> TestClient:
    return TestClient(create_app(settings, session_factory=session_factory))
```

- [ ] **Step 2: Write failing tests**

`tests/test_user_api.py`
```python
import pytest

BASE = "/api/v1/users"
CREDS = {
    "email": "ann@example.com",
    "password": "pw123456",
    "first_name": "Ann",
    "last_name": "Lee",
}


def register(client, **overrides):
    return client.post(f"{BASE}/register", json={**CREDS, **overrides})


def login(client):
    return client.post(
        f"{BASE}/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_201_bare_entity(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "email", "first_name", "last_name", "created_at", "updated_at"}
    assert "password" not in body


def test_register_bad_email_400_users_001(client):
    r = register(client, email="nope")
    assert r.status_code == 400
    assert r.json() == {"trace_id": "users-001", "message": "email pattern is invalid"}


def test_register_malformed_body_400_users_001(client):
    r = client.post(f"{BASE}/register", json={"email": "a@b.co"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-001"


def test_register_long_password_400(client):
    r = register(client, password="x" * 80)
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-001"


def test_register_duplicate_409(client):
    register(client)
    r = register(client)
    assert r.status_code == 409
    assert r.json()["trace_id"] == "users-001"


def test_login_shape(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"user", "token"}
    assert set(body["token"]) == {"access", "refresh"}


def test_login_wrong_password_400_users_002(client):
    register(client)
    r = client.post(f"{BASE}/login", json={"email": CREDS["email"], "password": "bad"})
    assert r.status_code == 400
    assert r.json() == {"trace_id": "users-002", "message": "password is invalid"}


def test_profile_requires_valid_token(client):
    register(client)
    token = login(client).json()["token"]["access"]
    r = client.post(f"{BASE}/profile", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == CREDS["email"]


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "bearer abc"},
        {"Authorization": "Bearer abc"},
        {"Authorization": "Basic abc"},
    ],
)
def test_profile_bad_auth_header_is_401_envelope(client, headers):
    # Review focus: never 422/500, always the error envelope.
    r = client.post(f"{BASE}/profile", headers=headers)
    assert r.status_code == 401
    body = r.json()
    assert body["trace_id"] == "middlware-002"
    assert body["message"]


def test_refresh_flow(client):
    register(client)
    tokens = login(client).json()["token"]
    r = client.post(f"{BASE}/refresh-token", json={"refresh_token": tokens["refresh"]})
    assert r.status_code == 200
    new_access = r.json()["token"]["access"]
    assert client.post(f"{BASE}/profile", headers=auth(new_access)).status_code == 200


def test_refresh_bad_token_400_users_003(client):
    r = client.post(f"{BASE}/refresh-token", json={"refresh_token": "abc"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-003"


def test_logout_then_profile_401(client):
    register(client)
    tokens = login(client).json()["token"]
    r = client.post(f"{BASE}/logout", json={"refresh_token": tokens["refresh"]})
    assert r.status_code == 200
    assert client.post(f"{BASE}/profile", headers=auth(tokens["access"])).status_code == 401


def test_logout_bad_token_400_users_004(client):
    r = client.post(f"{BASE}/logout", json={"refresh_token": "abc"})
    assert r.status_code == 400
    assert r.json()["trace_id"] == "users-004"
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_user_api.py -v`
Expected: FAIL (`create_app() got an unexpected keyword argument 'session_factory'`).

- [ ] **Step 4: Implement deps**

`src/app/infrastructure/api/deps.py`
```python
from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.entities.user import UserEntity
from app.domain.errors import AuthError
from app.infrastructure.api.errors import ApiError
from app.interface.repositories.postgres_user import PostgresUserRepository
from app.shared.security import TokenService
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
```

- [ ] **Step 5: Implement handlers**

`src/app/interface/handlers/user.py`
```python
from fastapi import APIRouter, Depends

from app.domain.entities.user import (
    UserEntity,
    UserLoginRequest,
    UserLoginResponse,
    UserRefreshTokenRequest,
    UserRegisterRequest,
)
from app.domain.errors import ConflictError, DomainError
from app.infrastructure.api.deps import get_user_usecase, require_user
from app.infrastructure.api.errors import ApiError
from app.usecases.user import UserUsecase

REGISTER_ERROR = "users-001"
LOGIN_ERROR = "users-002"
REFRESH_ERROR = "users-003"
LOGOUT_ERROR = "users-004"


def build_user_router() -> APIRouter:
    router = APIRouter(prefix="/users", tags=["User"])

    @router.post("/register", status_code=201, response_model=UserEntity)
    def register(
        req: UserRegisterRequest, usecase: UserUsecase = Depends(get_user_usecase)
    ) -> UserEntity:
        try:
            return usecase.register(req)
        except ConflictError as exc:
            raise ApiError(409, REGISTER_ERROR, str(exc)) from exc
        except DomainError as exc:
            raise ApiError(400, REGISTER_ERROR, str(exc)) from exc

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
```

- [ ] **Step 6: Wire into `create_app`**

Replace `src/app/infrastructure/api/main.py` with:
```python
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.infrastructure.api.errors import install_error_handlers
from app.infrastructure.db.postgres import build_session_factory
from app.interface.handlers.monitor import build_monitor_router
from app.interface.handlers.user import build_user_router


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    app = FastAPI(title=settings.goapp_name, version=settings.goapp_version)
    app.state.settings = settings
    app.state.session_factory = session_factory or build_session_factory(settings.postgres_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "HEAD", "PUT", "DELETE", "PATCH"],
        allow_headers=[],
        allow_credentials=False,
    )
    install_error_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(build_monitor_router(settings))
    api_v1.include_router(build_user_router())
    app.include_router(api_v1)
    return app
```

- [ ] **Step 7: Run all tests**

Run: `pytest -q`
Expected: all pass. Task 1's `test_monitor_api.py` calls `create_app(settings)` without a session factory; `build_session_factory` is lazy (no connection at engine creation) so it still passes without Postgres. If psycopg import fails in the environment, install `psycopg[binary]`.

- [ ] **Step 8: Commit**

```bash
git add 
git commit -m "feat(python): user endpoints with JWT auth dependency"
```

---

### Task 6: Generic CRUD (Postgres): registry, describe, list, get

**Files:**
- Create: `src/app/shared/slug.py`, `src/app/shared/schema.py`
- Create: `src/app/domain/entities/crud.py`, `src/app/domain/repositories/crud.py`
- Create: `src/app/interface/repositories/postgres_crud.py`, `src/app/interface/repositories/crud_factory.py`
- Create: `src/app/usecases/crud.py`, `src/app/interface/handlers/crud.py`
- Create: `src/app/infrastructure/api/registry.py`
- Modify: `src/app/infrastructure/api/deps.py`, `src/app/infrastructure/api/main.py`
- Test: `tests/test_crud_slug_schema.py`, `tests/test_crud_api.py`

**Interfaces:**
- Consumes: `UserModel`, `UserPermissionModel`, `Base`, `require_user`, `get_session`, `ApiError`.
- Produces:
  - `to_crud_slug(name: str) -> str` (`user_permissions` → `user-permissions`; `UserModel` → `user-model`).
  - `class Datasource(str, Enum)`: `POSTGRESQL`, `MONGODB`.
  - `@dataclass(frozen=True) class CrudResource: name: str; datasource: Datasource; model: type; hidden: frozenset[str] = frozenset()`; property `slug`.
  - `DataResponse(code: int = 0, data: Any, message: str = "", data_schema: dict | None)`; `DataListResponse(code=0, data: list, page, page_size, total_page, total_data, message="", data_schema)` (pydantic; JSON keys identical to Go).
  - `ICrudRepository` (ABC): `get_one_by_id(id: str) -> DataResponse`; `get_list(page: int, page_size: int, filter: dict[str, Any] | None) -> DataListResponse`; `describe(schema: str) -> dict[str, Any]`. (Create/update/delete are out of scope: Go has no routes for them.)
  - `describe_resource(resource: CrudResource) -> dict` → `{"type":"record","name":<slug of model class name>,"fields":[{"name":..,"type":..}]}` with SQLAlchemy `String→"string"`, `Integer→"int"`, `Boolean→"boolean"`, `DateTime→"datetime"`, hidden fields omitted.
  - `CrudRepositoryFactory(resources: list[CrudResource], session: Session, mongo_db: Database | None)` with `.get(slug: str) -> ICrudRepository`; unknown slug raises `NotFoundError("Entity model not found")`.
  - `CRUD_RESOURCES: list[CrudResource]` = `users` (hidden `password`) and `user_permissions`; `user_tokens` deliberately excluded.
  - `parse_pagination(query: Mapping[str, str]) -> tuple[int, int]` in `handlers/crud.py`.

- [ ] **Step 1: Write failing tests for slug/schema/pagination**

`tests/test_crud_slug_schema.py`
```python
import pytest

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.models.user import UserModel
from app.interface.handlers.crud import parse_pagination
from app.shared.schema import describe_resource
from app.shared.slug import to_crud_slug


@pytest.mark.parametrize(
    "name,slug",
    [("users", "users"), ("user_permissions", "user-permissions"), ("UserModel", "user-model")],
)
def test_slug(name, slug):
    assert to_crud_slug(name) == slug


def test_describe_hides_password_and_maps_types():
    res = CrudResource("users", Datasource.POSTGRESQL, UserModel, hidden=frozenset({"password"}))
    schema = describe_resource(res)
    assert schema["type"] == "record"
    assert schema["name"] == "user-model"
    fields = {f["name"]: f["type"] for f in schema["fields"]}
    assert fields["id"] == "int"
    assert fields["email"] == "string"
    assert fields["created_at"] == "datetime"
    assert "password" not in fields


@pytest.mark.parametrize(
    "query,expected",
    [
        ({}, (1, 10)),
        ({"_page": "3", "_pageSize": "25"}, (3, 25)),
        ({"_pageSize": "0"}, (1, 10)),
        ({"_pageSize": "-5"}, (1, 10)),
        ({"_pageSize": "99999"}, (1, 1000)),
        ({"_pageSize": "abc"}, (1, 10)),
        ({"_page": "0"}, (1, 10)),
        ({"_page": "-2"}, (1, 10)),
        ({"_page": "abc"}, (1, 10)),
    ],
)
def test_parse_pagination_clamps(query, expected):
    assert parse_pagination(query) == expected
```

- [ ] **Step 2: Write failing API tests**

`tests/test_crud_api.py`
```python
import pytest

from app.domain.models.user import UserPermissionModel

CREDS = {
    "email": "ann@example.com",
    "password": "pw123456",
    "first_name": "Ann",
    "last_name": "Lee",
}


@pytest.fixture
def token(client):
    client.post("/api/v1/users/register", json=CREDS)
    r = client.post(
        "/api/v1/users/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    return r.json()["token"]["access"]


@pytest.fixture
def h(token):
    return {"Authorization": f"Bearer {token}"}


def test_requires_auth(client):
    assert client.get("/api/v1/data/users/").status_code == 401


def test_list_shape_and_no_password(client, h):
    r = client.get("/api/v1/data/users/", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "code",
        "data",
        "page",
        "page_size",
        "total_page",
        "total_data",
        "message",
        "data_schema",
    }
    assert body["page"] == 1 and body["page_size"] == 10
    assert body["total_data"] == 1 and body["total_page"] == 1
    assert body["data"][0]["email"] == CREDS["email"]
    assert "password" not in body["data"][0]


def test_list_pagination_counts_are_real(client, session_factory, h):
    with session_factory() as s:
        for i in range(24):
            s.add(UserPermissionModel(user_id=None, permission=f"p{i}"))
        s.commit()
    r = client.get("/api/v1/data/user-permissions/?_page=2&_pageSize=10", headers=h)
    body = r.json()
    assert len(body["data"]) == 10
    assert body["total_data"] == 24
    assert body["total_page"] == 3
    assert body["page"] == 2


@pytest.mark.parametrize(
    "qs", ["_pageSize=-5", "_pageSize=0", "_pageSize=abc", "_page=0", "_page=abc"]
)
def test_list_bad_pagination_is_clamped(client, h, qs):
    r = client.get(f"/api/v1/data/users/?{qs}", headers=h)
    assert r.status_code == 200
    assert r.json()["page"] == 1
    assert r.json()["page_size"] == 10


def test_trailing_slash_optional(client, h):
    # Review focus: Fiber serves both; Starlette would 307-redirect by default.
    a = client.get("/api/v1/data/users", headers=h, follow_redirects=False)
    b = client.get("/api/v1/data/users/", headers=h, follow_redirects=False)
    assert a.status_code == 200 and b.status_code == 200


def test_get_one(client, h):
    uid = client.get("/api/v1/data/users/", headers=h).json()["data"][0]["id"]
    r = client.get(f"/api/v1/data/users/{uid}", headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["email"] == CREDS["email"]
    assert "password" not in r.json()["data"]
    assert r.json()["data_schema"]["type"] == "record"


def test_get_one_missing_or_bad_id_is_400_error_trace(client, h):
    for path in ("/api/v1/data/users/9999", "/api/v1/data/users/abc"):
        r = client.get(path, headers=h)
        assert r.status_code == 400
        assert r.json()["trace_id"] == "error"


def test_unknown_slug_400(client, h):
    r = client.get("/api/v1/data/nope/", headers=h)
    assert r.status_code == 400
    assert r.json() == {"trace_id": "error", "message": "Entity model not found"}


def test_user_tokens_not_exposed(client, h):
    # Deviation 4: Go would leak every user's access/refresh token here.
    r = client.get("/api/v1/data/user-tokens/", headers=h)
    assert r.status_code == 400


def test_describe_route_not_shadowed_by_id_route(client, h):
    r = client.get("/api/v1/data/users/describe", headers=h)
    assert r.status_code == 200
    assert r.json()["type"] == "record"


def test_user_without_permission_row_can_read(client, h):
    assert client.get("/api/v1/data/users/", headers=h).status_code == 200
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_crud_slug_schema.py tests/test_crud_api.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4: Implement shared helpers and domain**

`src/app/shared/slug.py`
```python
import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def to_crud_slug(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower().replace("_", "-")
```

`src/app/domain/entities/crud.py`
```python
from dataclasses import dataclass
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
```

`src/app/shared/schema.py`
```python
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.inspection import inspect

from app.domain.entities.crud import CrudResource
from app.shared.slug import to_crud_slug


def _sa_type(column_type: Any) -> str:
    if isinstance(column_type, Boolean):
        return "boolean"
    if isinstance(column_type, Integer):
        return "int"
    if isinstance(column_type, DateTime):
        return "datetime"
    return "string"


_PY_TYPES = {int: "int", bool: "boolean", str: "string", dict: "map"}


def describe_resource(resource: CrudResource) -> dict[str, Any]:
    fields: list[dict[str, str]] = []
    if hasattr(resource.model, "__table__"):
        for column in inspect(resource.model).columns:
            if column.key not in resource.hidden:
                fields.append({"name": column.key, "type": _sa_type(column.type)})
    else:  # pydantic document model (Mongo)
        for name, info in resource.model.model_fields.items():  # type: ignore[attr-defined]
            if name not in resource.hidden:
                fields.append({"name": name, "type": _PY_TYPES.get(info.annotation, "string")})
    return {"type": "record", "name": to_crud_slug(resource.model.__name__), "fields": fields}
```

`src/app/domain/repositories/crud.py`
```python
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
```

- [ ] **Step 5: Implement Postgres CRUD repo, factory, registry**

`src/app/interface/repositories/postgres_crud.py`
```python
import math
from typing import Any

from sqlalchemy import func, select
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
            c.key: getattr(row, c.key) for c in row.__table__.columns if c.key not in self._r.hidden
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
        model = self._r.model
        total = self._s.scalar(select(func.count()).select_from(model)) or 0
        rows = self._s.scalars(
            select(model).order_by(model.id).offset((page - 1) * page_size).limit(page_size)  # type: ignore[attr-defined]
        ).all()
        return DataListResponse(
            data=[self._serialize(r) for r in rows],
            page=page,
            page_size=page_size,
            total_page=math.ceil(total / page_size),
            total_data=total,
            data_schema=self.describe("list"),
        )

    def describe(self, schema: str) -> dict[str, Any]:
        return describe_resource(self._r)
```

`src/app/interface/repositories/crud_factory.py`
```python
from sqlalchemy.orm import Session

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.errors import NotFoundError
from app.domain.repositories.crud import ICrudRepository
from app.interface.repositories.postgres_crud import PostgresCrudRepository


class CrudRepositoryFactory:
    def __init__(self, resources: list[CrudResource], session: Session) -> None:
        self._by_slug = {r.slug: r for r in resources}
        self._session = session

    def get(self, slug: str) -> ICrudRepository:
        resource = self._by_slug.get(slug)
        if resource is None:
            raise NotFoundError("Entity model not found")
        if resource.datasource is Datasource.POSTGRESQL:
            return PostgresCrudRepository(resource, self._session)
        raise NotFoundError("Datasource not supported")
```

`src/app/infrastructure/api/registry.py`
```python
from app.domain.entities.crud import CrudResource, Datasource
from app.domain.models.user import UserModel, UserPermissionModel

# Add a CrudResource here to expose a new model under /api/v1/data/<slug>/.
# UserTokenModel is deliberately NOT listed: it holds live access/refresh tokens.
CRUD_RESOURCES: list[CrudResource] = [
    CrudResource("users", Datasource.POSTGRESQL, UserModel, hidden=frozenset({"password"})),
    CrudResource("user_permissions", Datasource.POSTGRESQL, UserPermissionModel),
]
```

- [ ] **Step 6: Implement usecase, handler, wiring**

`src/app/usecases/crud.py`
```python
from typing import Any

from app.domain.entities.crud import DataListResponse, DataResponse
from app.interface.repositories.crud_factory import CrudRepositoryFactory


class CrudUsecase:
    def __init__(self, factory: CrudRepositoryFactory) -> None:
        self._factory = factory

    def retrieve(self, slug: str, id: str) -> DataResponse:
        return self._factory.get(slug).get_one_by_id(id)

    def retrieve_list(self, slug: str, page: int, page_size: int) -> DataListResponse:
        return self._factory.get(slug).get_list(page, page_size, None)

    def describe(self, slug: str, schema: str = "") -> dict[str, Any]:
        return self._factory.get(slug).describe(schema)
```

`src/app/interface/handlers/crud.py`
```python
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.domain.entities.crud import DataListResponse, DataResponse
from app.domain.entities.user import UserEntity
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
    router = APIRouter(prefix="/data", tags=["CRUD"], dependencies=[Depends(require_user)])

    # describe must be registered before /{slug}/{id}
    @router.get("/{slug}/describe")
    def describe(slug: str, usecase: CrudUsecase = Depends(get_crud_usecase)) -> dict[str, Any]:
        try:
            return usecase.describe(slug)
        except DomainError as exc:
            raise ApiError(400, "error", str(exc)) from exc

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
```

Add to `src/app/infrastructure/api/deps.py` (new imports at top, function at bottom):
```python
from app.infrastructure.api.registry import CRUD_RESOURCES
from app.interface.repositories.crud_factory import CrudRepositoryFactory
from app.usecases.crud import CrudUsecase


def get_crud_usecase(session: Session = Depends(get_session)) -> CrudUsecase:
    return CrudUsecase(CrudRepositoryFactory(CRUD_RESOURCES, session))
```

In `main.py` add `from app.interface.handlers.crud import build_crud_router` and `api_v1.include_router(build_crud_router())` after the user router.

- [ ] **Step 7: Run all tests**

Run: `pytest -q`
Expected: all pass. If `test_trailing_slash_optional` returns 307, `redirect_slashes` is interfering: keep both decorators and confirm the no-slash route is registered *before* the slash one, or set `redirect_slashes=False` on the app router.

- [ ] **Step 8: Commit**

```bash
git add 
git commit -m "feat(python): generic CRUD read endpoints for Postgres resources"
```

---

### Task 7: Mongo CRUD repository

**Files:**
- Create: `src/app/infrastructure/db/mongo.py`, `src/app/interface/repositories/mongo_crud.py`
- Modify: `src/app/interface/repositories/crud_factory.py`, `src/app/infrastructure/api/deps.py`, `src/app/infrastructure/api/main.py`
- Test: `tests/test_mongo_crud.py`

**Interfaces:**
- Consumes: `CrudResource`, `ICrudRepository`, `CrudRepositoryFactory`.
- Produces:
  - `build_mongo_database(uri: str, name: str) -> Database | None` (returns `None` when `uri` is empty).
  - `MongoCrudRepository(resource: CrudResource, collection: Collection)`; documents are returned with `_id` renamed to `id` (hex string). **Assumption:** Go decodes into model structs with no JSON tags for `_id`, so the exact Go key is unknown; confirm against a real Mongo model before cutover.
  - `CrudRepositoryFactory(resources, session, mongo_db: Database | None = None)`.
  - `app.state.mongo_db` set in `create_app` and a `get_mongo_db(request)` dep; `get_crud_usecase` passes it to the factory.

- [ ] **Step 1: Write failing tests**

`tests/test_mongo_crud.py`
```python
import mongomock
import pytest
from bson import ObjectId
from pydantic import BaseModel

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.errors import NotFoundError, ValidationError
from app.interface.repositories.crud_factory import CrudRepositoryFactory
from app.interface.repositories.mongo_crud import MongoCrudRepository


class ProductDoc(BaseModel):
    name: str
    price: int


RESOURCE = CrudResource("products", Datasource.MONGODB, ProductDoc)


@pytest.fixture
def collection():
    col = mongomock.MongoClient().db["products"]
    col.insert_many([{"name": f"p{i}", "price": i} for i in range(25)])
    return col


def test_get_one_renames_id(collection):
    oid = str(collection.find_one({"name": "p3"})["_id"])
    res = MongoCrudRepository(RESOURCE, collection).get_one_by_id(oid)
    assert res.data["id"] == oid
    assert "_id" not in res.data
    assert res.data["name"] == "p3"


def test_get_one_bad_or_missing_id(collection):
    repo = MongoCrudRepository(RESOURCE, collection)
    with pytest.raises(ValidationError):
        repo.get_one_by_id("not-an-object-id")
    with pytest.raises(NotFoundError):
        repo.get_one_by_id(str(ObjectId()))


def test_get_list_paginates_with_real_totals(collection):
    res = MongoCrudRepository(RESOURCE, collection).get_list(3, 10, None)
    assert len(res.data) == 5
    assert res.total_data == 25
    assert res.total_page == 3
    assert res.page == 3


def test_describe_uses_pydantic_fields(collection):
    schema = MongoCrudRepository(RESOURCE, collection).describe("list")
    assert {f["name"]: f["type"] for f in schema["fields"]} == {"name": "string", "price": "int"}


def test_factory_routes_mongo_resources(collection, session):
    db = collection.database
    factory = CrudRepositoryFactory([RESOURCE], session, db)
    assert isinstance(factory.get("products"), MongoCrudRepository)


def test_factory_mongo_not_configured(session):
    factory = CrudRepositoryFactory([RESOURCE], session, None)
    with pytest.raises(NotFoundError, match="Datasource not supported"):
        factory.get("products")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_mongo_crud.py -v`
Expected: FAIL `ModuleNotFoundError: app.interface.repositories.mongo_crud`.

- [ ] **Step 3: Implement**

`src/app/infrastructure/db/mongo.py`
```python
from pymongo import MongoClient
from pymongo.database import Database


def build_mongo_database(uri: str, name: str) -> Database | None:  # type: ignore[type-arg]
    if not uri:
        return None
    return MongoClient(uri)[name]  # MongoClient connects lazily
```

`src/app/interface/repositories/mongo_crud.py`
```python
import math
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.domain.entities.crud import CrudResource, DataListResponse, DataResponse
from app.domain.errors import NotFoundError, ValidationError
from app.domain.repositories.crud import ICrudRepository
from app.shared.schema import describe_resource


class MongoCrudRepository(ICrudRepository):
    def __init__(self, resource: CrudResource, collection: Collection) -> None:  # type: ignore[type-arg]
        self._r = resource
        self._c = collection

    def _serialize(self, doc: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in doc.items() if k != "_id" and k not in self._r.hidden}
        out["id"] = str(doc["_id"])
        return out

    def get_one_by_id(self, id: str) -> DataResponse:
        try:
            oid = ObjectId(id)
        except (InvalidId, TypeError) as exc:
            raise ValidationError("invalid id") from exc
        doc = self._c.find_one({"_id": oid})
        if doc is None:
            raise NotFoundError("record not found")
        return DataResponse(data=self._serialize(doc), data_schema=self.describe("detail"))

    def get_list(
        self, page: int, page_size: int, filter: dict[str, Any] | None
    ) -> DataListResponse:
        query = filter or {}
        total = self._c.count_documents(query)
        docs = self._c.find(query).sort("_id", 1).skip((page - 1) * page_size).limit(page_size)
        return DataListResponse(
            data=[self._serialize(d) for d in docs],
            page=page,
            page_size=page_size,
            total_page=math.ceil(total / page_size),
            total_data=total,
            data_schema=self.describe("list"),
        )

    def describe(self, schema: str) -> dict[str, Any]:
        return describe_resource(self._r)
```

Replace `src/app/interface/repositories/crud_factory.py`:
```python
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.errors import NotFoundError
from app.domain.repositories.crud import ICrudRepository
from app.interface.repositories.mongo_crud import MongoCrudRepository
from app.interface.repositories.postgres_crud import PostgresCrudRepository


class CrudRepositoryFactory:
    def __init__(
        self,
        resources: list[CrudResource],
        session: Session,
        mongo_db: Database | None = None,  # type: ignore[type-arg]
    ) -> None:
        self._by_slug = {r.slug: r for r in resources}
        self._session = session
        self._mongo_db = mongo_db

    def get(self, slug: str) -> ICrudRepository:
        resource = self._by_slug.get(slug)
        if resource is None:
            raise NotFoundError("Entity model not found")
        if resource.datasource is Datasource.POSTGRESQL:
            return PostgresCrudRepository(resource, self._session)
        if resource.datasource is Datasource.MONGODB and self._mongo_db is not None:
            return MongoCrudRepository(resource, self._mongo_db[resource.name])
        raise NotFoundError("Datasource not supported")
```

In `deps.py` replace `get_crud_usecase` with:
```python
def get_crud_usecase(request: Request, session: Session = Depends(get_session)) -> CrudUsecase:
    return CrudUsecase(CrudRepositoryFactory(CRUD_RESOURCES, session, request.app.state.mongo_db))
```
In `main.py` add `from app.infrastructure.db.mongo import build_mongo_database` and, after the `session_factory` line:
```python
    app.state.mongo_db = build_mongo_database(
        settings.goapp_mongodb_db_atlas_uri, settings.goapp_mongodb_db_name
    )
```

- [ ] **Step 4: Run all tests**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add 
git commit -m "feat(python): Mongo CRUD repository behind the same factory"
```

---

### Task 8: Packaging, docs, and contract test against the Go service

**Files:**
- Create: `Dockerfile`, `.env.template`, `tests/contract/__init__.py` (empty), `tests/contract/test_go_parity.py`
- Modify: `docker-compose.yml` (add `api-python` service), `README.md` (add a "Python port" section)

**Interfaces:**
- Consumes: the whole app. Produces: `uvicorn app.infrastructure.api.main:create_app --factory` as the run command.

- [ ] **Step 1: Write the contract test (skipped unless both servers are up)**

`tests/contract/test_go_parity.py`
```python
"""Run with: GO_URL=http://127.0.0.1:3000 PY_URL=http://127.0.0.1:3001 pytest -m contract tests/contract

Both servers must point at the SAME Postgres and share GOAPP_SECRET_KEY / GOAPP_NAME.
"""

import os
import uuid

import httpx
import pytest

GO = os.environ.get("GO_URL", "")
PY = os.environ.get("PY_URL", "")
pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not (GO and PY), reason="set GO_URL and PY_URL"),
]

TIMESTAMPS = {"created_at", "updated_at"}


def shape(value):
    """Reduce JSON to key names and value types so ids/timestamps/tokens don't matter."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


@pytest.fixture(scope="module")
def creds():
    return {
        "email": f"parity-{uuid.uuid4().hex[:8]}@example.com",
        "password": "pw123456",
        "first_name": "P",
        "last_name": "T",
    }


def test_user_registered_in_go_can_login_in_python_and_vice_versa(creds):
    assert httpx.post(f"{GO}/api/v1/users/register", json=creds).status_code == 201
    login = {"email": creds["email"], "password": creds["password"]}
    go_login = httpx.post(f"{GO}/api/v1/users/login", json=login)
    py_login = httpx.post(f"{PY}/api/v1/users/login", json=login)
    assert go_login.status_code == py_login.status_code == 200
    assert shape(go_login.json()) == shape(py_login.json())


def test_token_from_python_is_accepted_by_go(creds):
    login = {"email": creds["email"], "password": creds["password"]}
    token = httpx.post(f"{PY}/api/v1/users/login", json=login).json()["token"]["access"]
    r = httpx.post(f"{GO}/api/v1/users/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == creds["email"]


@pytest.mark.parametrize("path", ["/api/v1/", "/api/v1/nope"])
def test_public_responses_have_same_shape(path):
    go, py = httpx.get(f"{GO}{path}"), httpx.get(f"{PY}{path}")
    assert go.status_code == py.status_code
    assert shape(go.json()) == shape(py.json())


def test_crud_list_shape_matches(creds):
    login = {"email": creds["email"], "password": creds["password"]}
    token = httpx.post(f"{PY}/api/v1/users/login", json=login).json()["token"]["access"]
    h = {"Authorization": f"Bearer {token}"}
    go = httpx.get(f"{GO}/api/v1/data/users/", headers=h)
    py = httpx.get(f"{PY}/api/v1/data/users/", headers=h)
    assert go.status_code == py.status_code == 200
    assert shape(go.json()) == shape(py.json())
```

- [ ] **Step 2: Create `Dockerfile` and `.env.template`**

`Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 3000
CMD ["uvicorn", "app.infrastructure.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "3000"]
```

`.env.template`: copy of `env.template` from the repo root (same `GOAPP_*` names).

- [ ] **Step 3: Add compose service**

Append under `services:` in `docker-compose.yml`:
```yaml
  api-python:
    build: ./python
    env_file: ./.env.dev
    environment:
      GOAPP_POSTGRES_DB_HOST: db
      GOAPP_MONGODB_DB_ATLAS_URI: mongodb://root:golang-first-api@mongodb:27017/?authSource=admin
    ports:
      - "3001:3000"
    depends_on:
      - db
      - mongodb
```

- [ ] **Step 4: Document in README**

Add a "Python port (``)" section to `README.md` with: install (`pip install -e ".[dev]"`), migrate (`python -m app.infrastructure.db.migrate`), run (`uvicorn app.infrastructure.api.main:create_app --factory --port 3001`), test (`pytest`), contract test command (from the test docstring), the five intentional deviations, and the sentence "Swagger: open `/docs`; the old `swag init` flow is not used by the Python service."

- [ ] **Step 5: Verify everything**

Run: `ruff check . && mypy src && pytest -q`
Expected: ruff clean, mypy clean (fix annotations rather than adding blanket ignores), all tests pass, contract tests reported as deselected.

Run (manual, needs `docker-compose up db` and both servers): `GO_URL=http://127.0.0.1:3000 PY_URL=http://127.0.0.1:3001 pytest -m contract tests/contract -v`
Expected: 5 passed. A failure here is the real signal; fix Python, or record a new intentional deviation in the README and the plan header.

- [ ] **Step 6: Commit**

```bash
git add  docker-compose.yml README.md
git commit -m "feat(python): Dockerfile, compose service, docs and Go parity contract tests"
```

---

## Self-Review

**Spec coverage** (against Global Constraints): `/api/v1` prefix and routes → T1, T5, T6; bare payload + error envelope + trace ids → T1, T5, T6; JWT shape/`aud`/`iss`/expiry → T2; bcrypt/Go-hash compat → T2 (T2 uses a real `$2a$` vector; T8's cross-login test checks hashes written by the actual Go binary); shared tables and one-token-row semantics → T3, T4; CRUD slug/pagination/ignored filter → T6; CORS → T1; five deviations → T4 (2), T2/T4 (1 is exercised by `test_refresh_token_uses_refresh_lifetime`), T6 (3, 4, 5). Mongo → T7. Swagger → intentionally replaced by `/docs`.

**Placeholders:** none; the one soft spot is the fake bcrypt vector noted above.

**Type consistency:** `TokenService.sign/parse`, `TokenClaims.user_id/expires_at`, `IUserRepository` method names, `CrudResource.slug`, `CrudRepositoryFactory.get`, `parse_pagination` and `get_crud_usecase` are named identically wherever used. `create_app(settings, session_factory=...)` is introduced in T5 and relied on by `conftest.client`.

**Review Focus:** each of the five lines has a test: aud → T2 `test_parse_accepts_token_with_aud_claim`; 72 bytes → T4 `test_register_rejects_password_over_72_bytes` and T5 `test_register_long_password_400`; pagination → T6 `test_parse_pagination_clamps`, `test_list_bad_pagination_is_clamped`; trailing slash → T6 `test_trailing_slash_optional`; auth header → T5 `test_profile_bad_auth_header_is_401_envelope`.

**Known risks the executor should watch:** PyJWT error-class mapping in T2 (adjust the message mapping, not the expected Go messages); SQLite in tests does not enforce Postgres timezone/FK behaviour, so T8's contract run against real Postgres is the real check; Mongo `id` key naming is an assumption (T7).
