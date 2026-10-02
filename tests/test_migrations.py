from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db.migrations import upgrade_database
from app.db.models import Base, Customer


def test_fresh_database_migrates_and_is_repeatable(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    upgrade_database(database_url)
    upgrade_database(database_url)
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"alembic_version", "customers", "audit_events", "human_reviews"} <= tables
    engine.dispose()


def test_existing_create_all_database_is_adopted(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Base.metadata.tables["human_reviews"].drop(engine)
    with Session(engine) as session:
        session.add(Customer(name="Existing", region="West", revenue=42))
        session.commit()

    upgrade_database(database_url)
    with Session(engine) as session:
        assert session.scalar(select(Customer.name)) == "Existing"
    assert "human_reviews" in inspect(engine).get_table_names()
    engine.dispose()