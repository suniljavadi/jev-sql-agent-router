import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db, init_db, make_engine
from app.db.seed import seed
from app.main import app


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jev_provider="mock", llm_provider="mock")


@pytest.fixture
def session(settings):
    engine = make_engine(settings.database_url)
    init_db(engine)
    with Session(engine) as database:
        seed(database)
        yield database
    engine.dispose()


@pytest.fixture
def client(session, settings):
    from app.api.routes import get_agent
    from app.services.agent_service import AgentService
    from app.services.jev_service import make_jev
    from app.services.llm_service import make_llm

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_agent] = lambda: AgentService(settings, make_llm(settings), make_jev(settings))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()