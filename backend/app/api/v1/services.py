from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Service
from app.services.application_service import get_service

router = APIRouter(prefix="/services", tags=["services"])


def _serialize(s: Service) -> dict:
    rules = s.eligibility_rules or {}
    return {
        "code": s.code, "name": s.name, "description": s.description,
        "department": s.department.name, "department_code": s.department.code,
        "required_categories": s.required_categories, "consent_purpose": s.consent_purpose,
        "consent_validity_days": s.consent_validity_days, "workflow_code": s.workflow_code,
        "form_schema": s.form_schema,
        "eligibility": {
            "ruleset": rules.get("code"), "demo": rules.get("demo", True), "disclaimer": rules.get("disclaimer"),
            "rules": [{"id": r["id"], "description": r.get("description")} for r in rules.get("rules", [])],
        } if rules else None,
    }


@router.get("", summary="Public catalogue of services available through the platform")
def list_services(db: Session = Depends(get_db)) -> list[dict]:
    return [_serialize(s) for s in db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.name))]


@router.get("/{code}", summary="Service details, form schema and eligibility rules")
def get_one(code: str, db: Session = Depends(get_db)) -> dict:
    return _serialize(get_service(db, code))
