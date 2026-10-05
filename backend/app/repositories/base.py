from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def paginate(db: Session, stmt: Select, *, limit: int, offset: int, order_by: Any) -> tuple[list[Any], int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.order_by(order_by).limit(limit).offset(offset)).unique().all()
    return list(rows), int(total)
