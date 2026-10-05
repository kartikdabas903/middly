from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, uuid_pk


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class Service(Base):
    """A citizen-facing service offered by a department through the platform."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), index=True, nullable=False)
    workflow_code: Mapped[str] = mapped_column(String(80), nullable=False)
    # Connector of the department's own system (applications are forwarded there).
    department_connector_key: Mapped[str | None] = mapped_column(String(60))
    required_categories: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    consent_purpose: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    consent_validity_days: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    eligibility_rules: Mapped[dict | None] = mapped_column(JSONB)
    form_schema: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    department: Mapped[Department] = relationship(lazy="joined")
