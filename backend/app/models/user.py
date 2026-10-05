from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class User(Base):
    """Local mirror of identity-provider accounts (provisioned just-in-time on login)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)  # = Keycloak `sub`
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    citizen_id: Mapped[str | None] = mapped_column(ForeignKey("citizens.citizen_id"), index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")
