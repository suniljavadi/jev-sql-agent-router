from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def upgrade_database(database_url: str | None = None) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    url = database_url or get_settings().database_url
    config.attributes["database_url"] = url
    command.upgrade(config, "head")