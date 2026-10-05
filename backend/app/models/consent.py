from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, uuid_pk
from app.models.department import Department


class Consent(Base):
    """A citizen's explicit, purpose-bound, time-bound permission for data sharing."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = uuid_pk()  # consent_id
    citizen_id: Mapped[str] = mapped_column(ForeignKey("citizens.citizen_id"), nullable=False)
    requesting_department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id"))
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", use_alter=True), index=True)
    data_categories: Mapped[list] = mapped_column(JSONB, nullable=False)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    granted_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    requesting_department: Mapped[Department] = relationship(lazy="joined")

    __table_args__ = (Index("ix_consents_citizen_status", "citizen_id", "status"),)


class ConsentAccessLog(Base):
    """Every attempt to access citizen data, allowed or denied, with the consent used."""

    __tablename__ = "consent_access_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    consent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("consents.id"), index=True)
    citizen_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    data_category: Mapped[str] = mapped_column(String(40), nullable=False)
    accessor: Mapped[str] = mapped_column(String(120), nullable=False)
    accessor_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"))
    purpose: Mapped[str | None] = mapped_column(String(300))
    connector_key: Mapped[str | None] = mapped_column(String(60))
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", use_alter=True))
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # ALLOWED / DENIED
    reason: Mapped[str | None] = mapped_column(String(300))
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    accessed_at: Mapped[datetime] = created_at_col()
