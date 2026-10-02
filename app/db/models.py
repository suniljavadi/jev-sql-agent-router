from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(50))
    revenue: Mapped[float] = mapped_column(Float)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_request: Mapped[str] = mapped_column(Text)
    generated_sql: Mapped[str | None] = mapped_column(Text)
    jev_decision: Mapped[dict | None] = mapped_column(JSON)
    jev_confidence: Mapped[float | None] = mapped_column(Float)
    selected_action: Mapped[str | None] = mapped_column(String(40))
    security_validation: Mapped[str] = mapped_column(String(100))
    execution_status: Mapped[str] = mapped_column(String(40))
    execution_time_ms: Mapped[float] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    rows: Mapped[list] = mapped_column(JSON, default=list)


class Review(Base):
    __tablename__ = "human_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audit_events.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_audit_id: Mapped[int | None] = mapped_column(ForeignKey("audit_events.id"))