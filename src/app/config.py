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
