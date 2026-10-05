from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import any_user, citizen_only, officer_roles
from app.core.security import Principal
from app.db.session import get_db
from app.repositories.queries import AuditRepository
from app.schemas.requests import (
    ApplicationCreate,
    ClarificationRequest,
    ClarificationResponse,
    ConsentCreate,
    OfficerDecision,
    WithdrawRequest,
)
from app.services import application_service as svc
from app.services import consent_service

router = APIRouter(prefix="/applications", tags=["applications"])


def _detail(db: Session, principal: Principal, app_id: str) -> dict:
    db.expire_all()  # pick up changes made by event consumers after commit
    app = svc.load(db, app_id)
    data = svc.detail(db, principal, app)
    db.commit()  # persist access logs written while checking consent
    return data


@router.post("", status_code=status.HTTP_201_CREATED, summary="Submit an application (minimal form; data fetched with consent)")
def create_application(body: ApplicationCreate, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    app = svc.create(db, principal, body.service_code, body.form_data)
    db.commit()
    return _detail(db, principal, str(app.id))


@router.get("", summary="Unified application tracking (scoped by role)")
def list_applications(
    status_filter: str | None = Query(default=None, alias="status", max_length=200),
    service: str | None = Query(default=None, max_length=60),
    q: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(any_user),
    db: Session = Depends(get_db),
) -> dict:
    apps, total = svc.list_for(db, principal, status=status_filter, service=service, q=q, limit=limit, offset=offset)
    instances = svc.instances_for(db, apps)
    return {"items": [svc.summary(a, instances.get(a.id)) for a in apps], "total": total, "limit": limit, "offset": offset}


@router.get("/{application_id}", summary="Application details, workflow timeline, sources, data quality and eligibility")
def get_application(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    return _detail(db, principal, application_id)


@router.post("/{application_id}/consent", summary="Grant consent for this application (shortcut for POST /consents)")
def grant_consent(application_id: str, body: ConsentCreate, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    app = svc.load(db, application_id)
    svc.grant_consent(db, principal, app, [c.value for c in body.data_categories])
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/process", summary="Run automated verification (fetch, normalise, validate, eligibility)")
def process_application(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    app = svc.load(db, application_id)
    svc.process(db, principal, app)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/retry", summary="Retry a step waiting for an unavailable department system")
def retry_application(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    return process_application(application_id, principal, db)


@router.post("/{application_id}/sync", summary="Synchronise status from the department system")
def sync_application(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    app = svc.load(db, application_id)
    svc.sync_external(db, principal, app)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/approve", summary="Officer: approve")
def approve(application_id: str, body: OfficerDecision, principal: Principal = Depends(officer_roles), db: Session = Depends(get_db)) -> dict:
    svc.officer_action(db, principal, svc.load(db, application_id), "APPROVE", body.remarks)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/reject", summary="Officer: reject (reason required)")
def reject(application_id: str, body: OfficerDecision, principal: Principal = Depends(officer_roles), db: Session = Depends(get_db)) -> dict:
    svc.officer_action(db, principal, svc.load(db, application_id), "REJECT", body.remarks)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/request-clarification", summary="Officer: ask the citizen for clarification")
def request_clarification(application_id: str, body: ClarificationRequest, principal: Principal = Depends(officer_roles), db: Session = Depends(get_db)) -> dict:
    svc.officer_action(db, principal, svc.load(db, application_id), "REQUEST_CLARIFICATION", body.question)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/clarification-response", summary="Citizen: respond to a clarification request")
def clarification_response(application_id: str, body: ClarificationResponse, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    svc.respond_clarification(db, principal, svc.load(db, application_id), body.response)
    db.commit()
    return _detail(db, principal, application_id)


@router.post("/{application_id}/withdraw", summary="Citizen: withdraw (also revokes the bound consent)")
def withdraw(application_id: str, body: WithdrawRequest, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    svc.withdraw(db, principal, svc.load(db, application_id), body.reason)
    db.commit()
    return _detail(db, principal, application_id)


@router.get("/{application_id}/audit-logs", summary="Audit trail of one application (officers, admins)")
def application_audit(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    app = svc.load(db, application_id)
    svc.authorize_view(principal, app)
    if not principal.is_staff:
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Audit logs are available to officers and administrators")
    rows, total = AuditRepository.search(db, resource_id=str(app.id), limit=200, offset=0)
    consent_rows = []
    if app.consent_id:
        consent_rows, _ = AuditRepository.search(db, resource_id=str(app.consent_id), limit=50, offset=0)
    items = sorted([serializers.audit_log(a) for a in rows + consent_rows], key=lambda a: a["id"], reverse=True)
    return {"items": items, "total": len(items)}


@router.get("/{application_id}/consent-access-logs", summary="Who accessed the citizen's data for this application")
def application_access_logs(application_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> list[dict]:
    app = svc.load(db, application_id)
    svc.authorize_view(principal, app)
    if not app.consent_id:
        return []
    return consent_service.serialize(db, db.get(consent_service.Consent, app.consent_id), include_logs=True)["access_logs"]
