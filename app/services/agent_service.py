import logging
from datetime import datetime, timezone
from time import perf_counter

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ProviderError, QueryTimeout, SecurityError
from app.models.decision_models import Action, JevDecision
from app.models.response_models import AgentResponse
from app.services.audit_service import AuditService
from app.services.decision_router import DecisionRouter
from app.services.jev_service import JevService
from app.services.llm_service import LLMProvider
from app.services.security_service import SecurityService
from app.services.sql_service import SQLService
from app.utils.helpers import elapsed_ms


logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, settings: Settings, llm: LLMProvider, jev: JevService):
        self.llm = llm
        self.jev = jev
        self.router = DecisionRouter(settings)
        self.security = SecurityService(settings)
        self.sql = SQLService(settings)
        self.audit = AuditService()

    async def handle(self, session: Session, user_request: str) -> AgentResponse:
        start = perf_counter()
        generated_sql: str | None = None
        jev_decision: JevDecision | None = None
        selected_action: Action | None = None
        security_validation = "not_checked"
        status = "pending"
        explanation = ""
        error_message: str | None = None
        rows: list[dict] = []
        try:
            generated = await self.llm.generate(user_request)
            generated_sql = generated.sql
            if generated_sql:
                try:
                    self.security.validate(generated_sql)
                    security_validation = "passed"
                except SecurityError:
                    security_validation = "blocked"
            jev_decision = await self.jev.decide(user_request, {
                "generated_sql": generated_sql, "intent": generated.intent,
                "security": security_validation,
            })
            route = self.router.route(jev_decision)
            selected_action = route.action
            explanation = route.reason
            if route.action in (Action.EXECUTE_SQL, Action.RETRY):
                if not generated_sql:
                    status = "rejected"
                    explanation = "No SQL was generated"
                elif security_validation == "blocked":
                    status = "rejected"
                    explanation = "SQL blocked by security policy"
                else:
                    check = self.security.validate(generated_sql, strict=route.extra_validation)
                    security_validation = check.status
                    rows = await run_in_threadpool(self.sql.execute, session, check.sql,
                                                   retry=route.action == Action.RETRY)
                    status = "success"
            elif route.action == Action.ASK_CLARIFICATION:
                status = "clarification_required"
            elif route.action == Action.HUMAN_REVIEW:
                status = "review_required"
            elif route.action == Action.SELECT_TOOL:
                rows = await run_in_threadpool(self.sql.describe_schema, session)
                status = "success"
                explanation = "Schema inspection selected instead of SQL execution"
            else:
                status = "rejected"
        except (ProviderError, QueryTimeout, SecurityError, SQLAlchemyError) as exc:
            session.rollback()
            status = "failed" if not isinstance(exc, SecurityError) else "rejected"
            error_message = str(exc)
            explanation = "Request failed closed; no further SQL will run"
            logger.warning("agent_request_failed status=%s error_type=%s", status, type(exc).__name__)
        response = AgentResponse(audit_id=0, timestamp=datetime.now(timezone.utc),
            user_request=user_request, generated_sql=generated_sql, jev_decision=jev_decision,
            selected_action=selected_action, security_validation=security_validation,
            execution_status=status, execution_time_ms=elapsed_ms(start), rows=rows,
            explanation=explanation, error_message=error_message)
        return await run_in_threadpool(self.audit.record, session, response)