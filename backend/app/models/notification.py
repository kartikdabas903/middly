from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, uuid_pk


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    citizen_id: Mapped[str | None] = mapped_column(ForeignKey("citizens.citizen_id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="APPLICATION")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), index=True)
    # Idempotency: one notification per source event.
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_APP")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
