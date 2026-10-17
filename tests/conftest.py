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


from collections.abc import Iterator  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.domain.models.user import Base  # noqa: E402


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


from fastapi.testclient import TestClient  # noqa: E402

from app.infrastructure.api.main import create_app  # noqa: E402


@pytest.fixture
def client(settings, session_factory) -> TestClient:
    return TestClient(create_app(settings, session_factory=session_factory))
