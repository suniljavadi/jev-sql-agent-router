from datetime import datetime, timezone
from time import perf_counter

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import QueryTimeout, ReviewConflict, ReviewNotFound, SecurityError
from app.db.models import Audit, Review
from app.models.decision_models import Action
from app.models.response_models import AgentResponse
from app.models.review_models import ReviewResponse
from app.services.audit_service import AuditService
from app.services.security_service import SecurityService
from app.services.sql_service import SQLService
from app.utils.helpers import elapsed_ms


class ReviewService:
    def __init__(self, settings: Settings) -> None:
        self.security = SecurityService(settings)
        self.sql = SQLService(settings)
        self.audit = AuditService()

    def get(self, session: Session, audit_id: int) -> ReviewResponse:
        review = session.scalar(select(Review).where(Review.audit_id == audit_id))
        if review is None:
            raise ReviewNotFound()
        original = session.get(Audit, audit_id)
        return ReviewResponse(
            audit_id=audit_id, status=review.status, reviewer=review.reviewer,
            reviewed_at=review.reviewed_at, resolution_audit_id=review.resolution_audit_id,
            user_request=original.user_request, generated_sql=original.generated_sql,
            confidence=original.jev_confidence,
        )

    def pending(self, session: Session) -> list[ReviewResponse]:
        ids = session.scalars(select(Review.audit_id).where(Review.status == "pending")
                              .order_by(Review.id).limit(100)).all()
        return [self.get(session, audit_id) for audit_id in ids]

    async def resolve(self, session: Session, audit_id: int, reviewer: str,
                      approve: bool) -> ReviewResponse:
        original = session.get(Audit, audit_id)
        review = session.scalar(select(Review).where(Review.audit_id == audit_id))
        if original is None or review is None:
            raise ReviewNotFound()
        if review.status != "pending":
            raise ReviewConflict("Review has already been claimed or resolved")
        if approve:
            if not original.generated_sql or original.security_validation == "blocked":
                raise ReviewConflict("No safe SQL is available for approval")
            try:
                self.security.validate(original.generated_sql, strict=True)
            except SecurityError as exc:
                raise ReviewConflict("SQL failed strict read-only review validation") from exc
        claimed_at = datetime.now(timezone.utc)
        claimed = session.execute(update(Review).where(
            Review.audit_id == audit_id, Review.status == "pending"
        ).values(status="processing", reviewer=reviewer, reviewed_at=claimed_at))
        if claimed.rowcount != 1:
            session.rollback()
            raise ReviewConflict("Review has already been claimed or resolved")
        session.commit()

        start = perf_counter()
        rows: list[dict] = []
        status = "review_rejected"
        error_message: str | None = None
        validation = "not_executed"
        if approve:
            try:
                check = self.security.validate(original.generated_sql, strict=True)
                validation = check.status
                rows = await run_in_threadpool(self.sql.execute, session, check.sql)
                status = "success"
            except (SecurityError, QueryTimeout, SQLAlchemyError) as exc:
                session.rollback()
                status = "failed"
                error_message = str(exc)
        response = AgentResponse(
            audit_id=0, timestamp=datetime.now(timezone.utc),
            user_request=original.user_request, generated_sql=original.generated_sql,
            jev_decision=original.jev_decision,
            selected_action=Action.EXECUTE_SQL if approve else Action.HUMAN_REVIEW,
            security_validation=validation, execution_status=status,
            execution_time_ms=elapsed_ms(start), rows=rows,
            explanation=f"Review {('approved' if approve else 'rejected')} by {reviewer}; source audit {audit_id}",
            error_message=error_message,
        )
        resolution = await run_in_threadpool(self.audit.record, session, response)
        review.status = "approved" if status == "success" else "failed" if approve else "rejected"
        review.resolution_audit_id = resolution.audit_id
        session.commit()
        return self.get(session, audit_id)