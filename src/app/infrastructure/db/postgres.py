from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_session_factory(url: str) -> sessionmaker[Session]:
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)
