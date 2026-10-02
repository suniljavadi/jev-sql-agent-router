import pytest
from sqlalchemy.exc import OperationalError

from app.services.sql_service import SQLService


def test_select(session, settings):
    assert len(SQLService(settings).execute(session, "SELECT * FROM customers")) == 3


def test_invalid_sql(session, settings):
    with pytest.raises(OperationalError):
        SQLService(settings).execute(session, "SELECT missing FROM customers")


def test_invalid_query_audited(client):
    body = client.post("/api/query", json={"user_request": "invalid customers"}).json()
    assert body["execution_status"] == "failed"
    assert body["audit_id"] > 0


def test_destructive_request_not_executed(client):
    body = client.post("/api/query", json={"user_request": "delete customers"}).json()
    assert body["security_validation"] == "blocked"
    assert body["execution_status"] == "rejected"


def test_retry_only_transient(session, settings, monkeypatch):
    original = session.connection
    count = 0

    def flaky_connection():
        nonlocal count
        count += 1
        if count == 1:
            raise OperationalError("SELECT 1", {}, Exception("database is locked"))
        return original()

    monkeypatch.setattr(session, "connection", flaky_connection)
    assert SQLService(settings).execute(session, "SELECT 1", retry=True) == [{"1": 1}]
    assert count == 2


def test_database_timeout(session, settings, monkeypatch):
    from app.core.exceptions import QueryTimeout

    def timeout():
        raise OperationalError("SELECT 1", {}, Exception("interrupted"))

    monkeypatch.setattr(session, "connection", timeout)
    with pytest.raises(QueryTimeout):
        SQLService(settings).execute(session, "SELECT 1")


def test_database_timeout_is_audited(client, monkeypatch):
    from app.core.exceptions import QueryTimeout

    def timeout(self, session, sql, retry=False):
        raise QueryTimeout("Database query timed out")

    monkeypatch.setattr(SQLService, "execute", timeout)
    result = client.post("/api/query", json={"user_request": "count customers"}).json()
    assert result["execution_status"] == "failed"
    assert result["error_message"] == "Database query timed out"
    assert client.get(f"/api/decisions/{result['audit_id']}").json()["execution_status"] == "failed"