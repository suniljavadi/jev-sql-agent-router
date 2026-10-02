from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_api_access
from app.db.database import get_db
from app.models.response_models import AuditResponse
from app.services.audit_service import AuditService


router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decisions/{audit_id}", response_model=AuditResponse,
            dependencies=[Depends(require_api_access)])
def get_decision(audit_id: int, session: Session = Depends(get_db)) -> AuditResponse:
    result = AuditService().get(session, audit_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return AuditResponse.model_validate(result.model_dump())