from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./jev_agent.db")
    jev_provider: str = os.getenv("JEV_PROVIDER", "mock")
    jev_base_url: str = os.getenv("JEV_BASE_URL", "")
    jev_model: str = os.getenv("JEV_MODEL", "")
    typesafe_api_key: str = os.getenv("TYPESAFE_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    auto_execute_threshold: float = float(os.getenv("AUTO_EXECUTE_THRESHOLD", "0.90"))
    review_threshold: float = float(os.getenv("REVIEW_THRESHOLD", "0.70"))
    allow_destructive_sql: bool = os.getenv("ALLOW_DESTRUCTIVE_SQL", "false").lower() == "true"
    query_timeout_seconds: float = float(os.getenv("QUERY_TIMEOUT_SECONDS", "5"))
    external_timeout_seconds: float = float(os.getenv("EXTERNAL_TIMEOUT_SECONDS", "10"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    max_rows: int = int(os.getenv("MAX_ROWS", "100"))
    sql_allowed_tables: str = os.getenv("SQL_ALLOWED_TABLES", "customers")
    api_key: str = os.getenv("API_KEY", "")
    reviewer_api_key: str = os.getenv("REVIEWER_API_KEY", "")

    def __post_init__(self) -> None:
        if not 0 <= self.review_threshold < self.auto_execute_threshold <= 1:
            raise ValueError("Invalid confidence thresholds")
        if self.query_timeout_seconds <= 0 or self.external_timeout_seconds <= 0:
            raise ValueError("Timeouts must be positive")
        if self.max_retries < 0 or self.max_rows < 1:
            raise ValueError("Invalid retry or row limit")
        if self.api_key and self.api_key == self.reviewer_api_key:
            raise ValueError("API_KEY and REVIEWER_API_KEY must differ")
        if any(value.lower().startswith("replace-with-") for value in (self.api_key, self.reviewer_api_key)):
            raise ValueError("Replace sample API keys with generated secrets")
        if (self.jev_provider != "mock" or self.llm_provider != "mock") and not (
            self.api_key and self.reviewer_api_key
        ):
            raise ValueError("Live providers require API_KEY and REVIEWER_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()