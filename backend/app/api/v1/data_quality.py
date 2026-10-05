from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import admin_roles
from app.core import clock
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.models import DataQualityIssue
from app.repositories.queries import DataQualityRepository
from app.schemas.requests import ResolveIssue
from app.services.audit_service import audit

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/issues", summary="Data-quality issues detected during aggregation")
def issues(status: str | None = Query("OPEN", max_length=20), issue_type: str | None = Query(None, max_length=40),
           severity: str | None = Query(None, max_length=20), citizen_id: str | None = Query(None, max_length=20),
           limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
           _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    rows, total = DataQualityRepository.search(db, status=status or None, issue_type=issue_type, severity=severity,
                                               citizen_id=citizen_id, limit=limit, offset=offset)
    return {"items": [serializers.dq_issue(i) for i in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/summary", summary="Data-quality status by source system")
def summary(_: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    return DataQualityRepository.summary(db)


@router.post("/issues/{issue_id}/resolve", summary="Mark an issue as reviewed/resolved (source records are never edited)")
def resolve(issue_id: uuid.UUID, body: ResolveIssue, principal: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    issue = db.get(DataQualityIssue, issue_id)
    if issue is None:
        raise NotFoundError("Issue not found")
    issue.status = "RESOLVED"
    issue.resolved_at = clock.now()
    issue.resolved_by = principal.username
    issue.details = {**(issue.details or {}), "resolution_note": body.note}
    db.commit()
    audit("ADMIN_RESOLVED_DQ_ISSUE", "data_quality_issue", str(issue.id), details={"type": issue.issue_type, "note": body.note})
    return serializers.dq_issue(issue)
