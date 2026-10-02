from sqlalchemy.orm import Session

from app.db.models import Audit, Review
from app.models.response_models import AgentResponse


class AuditService:
    def record(self, session: Session, response: AgentResponse) -> AgentResponse:
        event = Audit(
            timestamp=response.timestamp, user_request=response.user_request,
            generated_sql=response.generated_sql,
            jev_decision=response.jev_decision.model_dump(mode="json") if response.jev_decision else None,
            jev_confidence=response.jev_decision.confidence if response.jev_decision else None,
            selected_action=response.selected_action.value if response.selected_action else None,
            security_validation=response.security_validation,
            execution_status=response.execution_status,
            execution_time_ms=response.execution_time_ms, error_message=response.error_message,
            explanation=response.explanation, rows=response.rows,
        )
        session.add(event)
        session.flush()
        if response.execution_status == "review_required":
            session.add(Review(audit_id=event.id, status="pending"))
        session.commit()
        session.refresh(event)
        return response.model_copy(update={"audit_id": event.id})

    def get(self, session: Session, audit_id: int) -> AgentResponse | None:
        event = session.get(Audit, audit_id)
        if event is None:
            return None
        return AgentResponse(audit_id=event.id, timestamp=event.timestamp,
            user_request=event.user_request, generated_sql=event.generated_sql,
            jev_decision=event.jev_decision, selected_action=event.selected_action,
            security_validation=event.security_validation, execution_status=event.execution_status,
            execution_time_ms=event.execution_time_ms, error_message=event.error_message,
            explanation=event.explanation, rows=event.rows)