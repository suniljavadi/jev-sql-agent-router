from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_api_access
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.request_models import AgentRequest
from app.models.response_models import AgentResponse
from app.services.agent_service import AgentService
from app.services.jev_service import make_jev
from app.services.llm_service import make_llm


router = APIRouter(prefix="/api", tags=["agent"])


def get_agent(settings: Settings = Depends(get_settings)) -> AgentService:
    return AgentService(settings, make_llm(settings), make_jev(settings))


@router.post("/query", response_model=AgentResponse, dependencies=[Depends(require_api_access)])
async def query(request: AgentRequest, session: Session = Depends(get_db),
                agent: AgentService = Depends(get_agent)) -> AgentResponse:
    return await agent.handle(session, request.user_request)