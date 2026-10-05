from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, updated_at_col


class Citizen(Base):
    """Canonical (golden) citizen record produced by master data management.

    Only the minimum needed for service delivery is stored; mobile numbers are
    masked and source identifiers (e.g. identity references) are never persisted.
    """

    __tablename__ = "citizens"

    citizen_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    mobile: Mapped[str | None] = mapped_column(String(20))  # masked, e.g. XXXXXX0001
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    pincode: Mapped[str | None] = mapped_column(String(10))
    education: Mapped[dict | None] = mapped_column(JSONB)
    employment_status: Mapped[str | None] = mapped_column(String(40))
    field_provenance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_status: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (Index("ix_citizens_name_dob", "full_name", "date_of_birth"),)
