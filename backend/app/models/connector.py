from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, updated_at_col, uuid_pk
from app.models.department import Department


class Connector(Base):
    """Registry entry for a department system connector (synced from plugins at startup)."""

    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"))
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(60), nullable=False)
    data_format: Mapped[str] = mapped_column(String(60), default="JSON", nullable=False)
    data_categories: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    plugin_module: Mapped[str] = mapped_column(String(300), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    last_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    department: Mapped[Department | None] = relationship(lazy="joined")


class ConnectorHealth(Base):
    __tablename__ = "connector_health"

    id: Mapped[uuid.UUID] = uuid_pk()
    connector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    circuit_state: Mapped[str] = mapped_column(String(20), default="CLOSED", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = created_at_col()


class ConnectorCall(Base):
    """Persisted log of each connector invocation (feeds the admin dashboard)."""

    __tablename__ = "connector_calls"

    id: Mapped[uuid.UUID] = uuid_pk()
    connector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCCESS / FAILURE / CIRCUIT_OPEN
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"))
    citizen_id: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = created_at_col()
