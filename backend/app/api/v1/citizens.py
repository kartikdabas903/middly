from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import any_user, citizen_only
from app.core.errors import ConsentRequiredError, ForbiddenError, NotFoundError
from app.core.security import Principal, Role
from app.db.session import get_db
from app.models import Citizen, DataQualityIssue, Department
from app.services import consent_service, data_access_service
from app.services.audit_service import audit
from app.api import serializers

router = APIRouter(prefix="/citizens", tags=["citizens"])


def _profile(db: Session, c: Citizen) -> dict:
    issues = db.scalars(select(DataQualityIssue).where(DataQualityIssue.citizen_id == c.citizen_id, DataQualityIssue.status == "OPEN")
                        .order_by(DataQualityIssue.detected_at.desc())).all()
    return {
        "citizen_id": c.citizen_id, "full_name": c.full_name, "date_of_birth": c.date_of_birth, "gender": c.gender,
        "mobile": c.mobile, "email": c.email, "address": c.address, "district": c.district, "state": c.state,
        "pincode": c.pincode, "education": c.education, "employment_status": c.employment_status,
        "provenance": c.field_provenance, "sources": c.source_status, "quality_status": c.quality_status,
        "last_synced_at": c.last_synced_at, "open_issues": [serializers.dq_issue(i) for i in issues],
    }


@router.get("/me/profile", summary="Citizen: consolidated canonical profile with field provenance")
def my_profile(principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    citizen = db.get(Citizen, principal.citizen_id or "")
    if citizen is None:
        raise NotFoundError("Citizen record not found")
    return _profile(db, citizen)


@router.post("/me/profile/refresh", summary="Citizen: re-fetch own records from every department and re-run data-quality checks")
def refresh_profile(principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    if not principal.citizen_id:
        raise ForbiddenError("No citizen ID linked to this account")
    _, report, unavailable = data_access_service.refresh_own_profile(db, principal.citizen_id, principal.username)
    db.commit()
    data = _profile(db, db.get(Citizen, principal.citizen_id))
    data["unavailable_sources"] = unavailable
    return data


@router.get("/{citizen_id}/profile", summary="Consolidated profile (self, or department staff with active consent)")
def citizen_profile(citizen_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise NotFoundError("Citizen not found")
    if principal.citizen_id == citizen_id:
        return _profile(db, citizen)
    if not principal.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN) or not principal.department_code:
        raise ForbiddenError("Only the citizen or a department with consent can view this profile")
    dept_id = db.scalar(select(Department.id).where(Department.code == principal.department_code))
    try:
        consent_service.verify(db, citizen_id=citizen_id, department_id=dept_id, category="IDENTITY", purpose="Officer profile view")
    except ConsentRequiredError:
        db.commit()  # keep the DENIED access log
        raise
    audit("OFFICER_VIEWED_CITIZEN_PROFILE", "citizen", citizen_id)
    db.commit()
    return _profile(db, citizen)
