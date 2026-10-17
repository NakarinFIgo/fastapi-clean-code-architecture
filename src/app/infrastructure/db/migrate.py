from sqlalchemy import Engine, create_engine

from app.config import Settings
from app.domain.models.user import Base


def create_tables(engine: Engine) -> None:
    """create_all skips tables that already exist, so it is safe on a DB the Go app migrated."""
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    engine = create_engine(Settings().postgres_url)
    create_tables(engine)
    print("Migration success !!!")
