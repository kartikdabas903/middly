from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, updated_at_col, uuid_pk


class WorkflowDefinition(Base):
    """Versioned, JSON-configured workflow (see /workflow-engine/definitions)."""

    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (UniqueConstraint("code", "version", name="uq_workflow_definitions_code_version"),)


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[uuid.UUID] = uuid_pk()
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    current_step_key: Mapped[str | None] = mapped_column(String(60))
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    auto_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = updated_at_col()

    definition: Mapped[WorkflowDefinition] = relationship(lazy="joined")
    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="instance", order_by="WorkflowStep.sequence", lazy="selectin", cascade="all, delete-orphan"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = uuid_pk()
    instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(60), nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = updated_at_col()

    instance: Mapped[WorkflowInstance] = relationship(back_populates="steps")

    __table_args__ = (UniqueConstraint("instance_id", "step_key", name="uq_workflow_steps_instance_step"),)
