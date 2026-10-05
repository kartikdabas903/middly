from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, updated_at_col, uuid_pk
from app.models.department import Department, Service


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = uuid_pk()
    application_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    citizen_id: Mapped[str] = mapped_column(ForeignKey("citizens.citizen_id"), index=True, nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True, nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    current_step: Mapped[str | None] = mapped_column(String(60))
    form_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    profile_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    eligibility_result: Mapped[dict | None] = mapped_column(JSONB)
    data_quality: Mapped[dict | None] = mapped_column(JSONB)
    consent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("consents.id"))
    department_reference: Mapped[str | None] = mapped_column(String(80))
    decision: Mapped[str | None] = mapped_column(String(20))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(120))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_seconds: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(String(120))
    submitted_at: Mapped[datetime] = created_at_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    service: Mapped[Service] = relationship(lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")
    history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application", order_by="ApplicationStatusHistory.created_at", lazy="selectin"
    )

    __table_args__ = (Index("ix_applications_department_status", "department_id", "status"),)


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    step: Mapped[str | None] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    application: Mapped[Application] = relationship(back_populates="history")


class ApplicationSequence(Base):
    """Per-year counters for human-readable application numbers (APP-2026-0001)."""

    __tablename__ = "application_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
