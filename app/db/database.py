from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Base


def make_engine(url: str):
    options = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    if url == "sqlite://":
        options["poolclass"] = StaticPool
    return create_engine(url, **options)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(db_engine=None) -> None:
    Base.metadata.create_all(db_engine or engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session