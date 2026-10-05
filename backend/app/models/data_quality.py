from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, uuid_pk


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[uuid.UUID] = uuid_pk()
    citizen_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), index=True)
    source_system: Mapped[str] = mapped_column(String(60), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    field: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    detected_at: Mapped[datetime] = created_at_col()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(120))
