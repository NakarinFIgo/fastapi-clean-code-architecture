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
