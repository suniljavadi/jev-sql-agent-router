from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReviewResolution(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)


class ReviewResponse(BaseModel):
    audit_id: int
    status: Literal["pending", "processing", "approved", "rejected", "failed"]
    reviewer: str | None
    reviewed_at: datetime | None
    resolution_audit_id: int | None
    user_request: str
    generated_sql: str | None
    confidence: float | None