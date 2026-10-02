from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_reviewer
from app.core.config import Settings, get_settings
from app.core.exceptions import ReviewConflict, ReviewNotFound
from app.db.database import get_db
from app.models.review_models import ReviewResolution, ReviewResponse
from app.services.review_service import ReviewService


router = APIRouter(prefix="/api/reviews", tags=["reviews"],
                   dependencies=[Depends(require_reviewer)])


def get_review_service(settings: Settings = Depends(get_settings)) -> ReviewService:
    return ReviewService(settings)


@router.get("", response_model=list[ReviewResponse])
def pending_reviews(session: Session = Depends(get_db),
                    service: ReviewService = Depends(get_review_service)) -> list[ReviewResponse]:
    return service.pending(session)


@router.get("/{audit_id}", response_model=ReviewResponse)
def get_review(audit_id: int, session: Session = Depends(get_db),
               service: ReviewService = Depends(get_review_service)) -> ReviewResponse:
    try:
        return service.get(session, audit_id)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc


async def resolve(audit_id: int, request: ReviewResolution, approve: bool,
                  session: Session, service: ReviewService) -> ReviewResponse:
    try:
        return await service.resolve(session, audit_id, request.reviewer, approve)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="Review not found") from exc
    except ReviewConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{audit_id}/approve", response_model=ReviewResponse)
async def approve(audit_id: int, request: ReviewResolution, session: Session = Depends(get_db),
                  service: ReviewService = Depends(get_review_service)) -> ReviewResponse:
    return await resolve(audit_id, request, True, session, service)


@router.post("/{audit_id}/reject", response_model=ReviewResponse)
async def reject(audit_id: int, request: ReviewResolution, session: Session = Depends(get_db),
                 service: ReviewService = Depends(get_review_service)) -> ReviewResponse:
    return await resolve(audit_id, request, False, session, service)