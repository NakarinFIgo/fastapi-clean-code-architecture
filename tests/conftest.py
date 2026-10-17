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
