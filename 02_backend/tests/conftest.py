from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.domain.models.user import Base
from app.infrastructure.api.main import create_app


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


@pytest.fixture
def client(settings: Settings, session_factory: sessionmaker[Session]) -> TestClient:
    return TestClient(create_app(settings, session_factory=session_factory))
