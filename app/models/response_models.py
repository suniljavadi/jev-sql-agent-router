from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.decision_models import Action, JevDecision


class AgentResponse(BaseModel):
    audit_id: int
    timestamp: datetime
    user_request: str
    generated_sql: str | None
    jev_decision: JevDecision | None
    selected_action: Action | None
    security_validation: str
    execution_status: str
    execution_time_ms: float
    rows: list[dict[str, Any]] = []
    explanation: str
    error_message: str | None = None


class AuditResponse(AgentResponse):
    pass