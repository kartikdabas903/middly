from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.db.base import Base


class AuditLog(Base):
    """Append-only audit trail.

    A database trigger rejects UPDATE/DELETE, and each row carries a SHA-256 hash
    chained to the previous row so tampering is detectable (/audit-logs/verify).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=clock.now, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80), index=True)
    source_system: Mapped[str | None] = mapped_column(String(80))
    destination_system: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_audit_logs_actor_ts", "actor", "timestamp"),)
