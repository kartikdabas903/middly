from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import platform_admin
from app.core.security import Principal
from app.db.session import get_db
from app.repositories.queries import AuditRepository
from app.services.audit_service import verify_chain

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", summary="Search the append-only audit trail")
def search(
    action: str | None = Query(None, max_length=80),
    actor: str | None = Query(None, max_length=120),
    resource: str | None = Query(None, max_length=60),
    resource_id: str | None = Query(None, max_length=80),
    correlation_id: str | None = Query(None, max_length=128),
    status: str | None = Query(None, max_length=20),
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    rows, total = AuditRepository.search(db, action=action, actor=actor, resource=resource, resource_id=resource_id,
                                         correlation_id=correlation_id, status=status, since=since, until=until, limit=limit, offset=offset)
    return {"items": [serializers.audit_log(a) for a in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/actions", summary="Distinct audit actions (for filters)")
def actions(_: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> list[str]:
    return AuditRepository.actions(db)


@router.get("/verify", summary="Verify the SHA-256 hash chain (tamper evidence)")
def verify(_: Principal = Depends(platform_admin)) -> dict:
    return verify_chain()
