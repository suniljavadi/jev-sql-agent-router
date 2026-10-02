from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.core.config import Settings
from app.core.exceptions import SecurityError


@dataclass(frozen=True)
class ValidationResult:
    status: str
    sql: str


class SecurityService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate(self, sql: str, strict: bool = False) -> ValidationResult:
        if not sql.strip() or "--" in sql or "/*" in sql or "*/" in sql:
            raise SecurityError("Empty SQL and SQL comments are not allowed")
        try:
            statements = parse(sql, read="postgres" if self.settings.database_url.startswith("postgres") else "sqlite")
        except ParseError as exc:
            raise SecurityError("Invalid SQL syntax") from exc
        if len(statements) != 1 or statements[0] is None:
            raise SecurityError("Exactly one SQL statement is required")
        statement = statements[0]
        forbidden = (exp.Delete, exp.Update, exp.Drop, exp.TruncateTable, exp.Alter,
                     exp.Create, exp.Grant, exp.Insert, exp.Command,
                     exp.Merge, exp.Transaction)
        destructive = any(isinstance(node, forbidden) for node in statement.walk())
        if destructive and (not self.settings.allow_destructive_sql or strict):
            raise SecurityError("Write or administrative SQL is blocked")
        if not destructive and not isinstance(statement, exp.Select):
            raise SecurityError("Only SELECT queries are allowed by default")
        if any(isinstance(node, exp.Into) for node in statement.walk()):
            raise SecurityError("SELECT INTO is blocked")
        cte_names = {cte.alias.lower() for cte in statement.find_all(exp.CTE)}
        allowed = {name.strip().lower() for name in self.settings.sql_allowed_tables.split(",") if name.strip()}
        for table in statement.find_all(exp.Table):
            if table.name.lower() not in allowed | cte_names or table.db or table.catalog:
                raise SecurityError("Table is not in SQL_ALLOWED_TABLES")
        if any(isinstance(node, exp.Func) and
               (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower() in
               {"pg_sleep", "dblink", "lo_export", "pg_read_file", "load_extension"}
               for node in statement.walk()):
            raise SecurityError("Unsafe SQL function is blocked")
        return ValidationResult("passed_strict" if strict else "passed", sql)