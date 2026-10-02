from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import QueryTimeout


class SQLService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def describe_schema(self, session: Session) -> list[dict[str, Any]]:
        inspector = inspect(session.get_bind())
        allowed = {name.strip().lower() for name in self.settings.sql_allowed_tables.split(",") if name.strip()}
        return [{"table": table, "columns": ", ".join(column["name"] for column in inspector.get_columns(table))}
                for table in inspector.get_table_names() if table.lower() in allowed]

    def execute(self, session: Session, sql: str, retry: bool = False) -> list[dict[str, Any]]:
        attempts = self.settings.max_retries + 1 if retry else 1
        for attempt in range(attempts):
            try:
                connection = session.connection()
                raw = connection.connection.driver_connection
                if connection.dialect.name == "sqlite":
                    from time import monotonic
                    deadline = monotonic() + self.settings.query_timeout_seconds
                    raw.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
                elif connection.dialect.name == "postgresql":
                    connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                                       {"timeout": str(int(self.settings.query_timeout_seconds * 1000))})
                try:
                    result = connection.execute(text(sql))
                    if not result.returns_rows:
                        session.commit()
                        return []
                    rows = [jsonable_encoder(dict(row._mapping)) for row in result.fetchmany(self.settings.max_rows)]
                    session.rollback()
                    return rows
                finally:
                    if connection.dialect.name == "sqlite":
                        raw.set_progress_handler(None, 0)
            except OperationalError as exc:
                session.rollback()
                if "interrupt" in str(exc).lower() or "timeout" in str(exc).lower():
                    raise QueryTimeout("Database query timed out") from exc
                if attempt == attempts - 1 or not (exc.connection_invalidated or
                        any(word in str(exc).lower() for word in ("locked", "temporarily unavailable", "deadlock"))):
                    raise
            except DBAPIError as exc:
                session.rollback()
                if attempt == attempts - 1 or not exc.connection_invalidated:
                    raise
            except SQLAlchemyError:
                session.rollback()
                raise
        raise RuntimeError("Retry attempts exhausted")