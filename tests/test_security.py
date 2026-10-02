import pytest

from app.core.config import Settings
from app.core.exceptions import SecurityError
from app.services.security_service import SecurityService


@pytest.mark.parametrize("sql", ["DROP TABLE customers", "TRUNCATE TABLE customers",
    "DELETE FROM customers", "UPDATE customers SET revenue=0", "ALTER TABLE customers ADD x INT",
    "CREATE USER bob", "GRANT SELECT ON customers TO bob", "REVOKE SELECT ON customers FROM bob",
    "SELECT * FROM customers; DELETE FROM customers", "SELECT * FROM customers -- comment",
    "WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x",
    "SELECT pg_sleep(1)", "SELECT load_extension('x')"])
def test_blocked_sql(settings, sql):
    with pytest.raises(SecurityError):
        SecurityService(settings).validate(sql)


def test_safe_select(settings):
    assert SecurityService(settings).validate("SELECT name FROM customers").status == "passed"


@pytest.mark.parametrize("sql", ["SELECT * FROM audit_events", "SELECT * FROM sqlite_master",
    "SELECT * FROM other.customers", "WITH x AS (SELECT * FROM audit_events) SELECT * FROM x"])
def test_private_tables_blocked(settings, sql):
    with pytest.raises(SecurityError):
        SecurityService(settings).validate(sql)


def test_explicit_write_opt_in():
    service = SecurityService(Settings(allow_destructive_sql=True))
    assert service.validate("DELETE FROM customers").status == "passed"
    with pytest.raises(SecurityError):
        service.validate("DELETE FROM customers", strict=True)