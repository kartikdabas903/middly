"""Consent management: explicit, purpose-bound, time-bound and revocable.

`verify()` is called before *every* access to citizen data; both allowed and
denied attempts are written to consent_access_logs.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import get_context
from app.core.errors import ConsentRequiredError, DomainValidationError, ForbiddenError, InvalidStateError, NotFoundError
from app.core.security import Principal
from app.events import outbox
from app.events.types import EventType
from app.models import Application, Consent, ConsentAccessLog, Department
from app.models.enums import ConsentStatus, DataCategory, TERMINAL_APPLICATION_STATUSES
from app.services.audit_service import audit

VALID_CATEGORIES = {c.value for c in DataCategory}


def _expire_if_needed(consent: Consent) -> Consent:
    if consent.status == ConsentStatus.ACTIVE and consent.expires_at <= clock.now():
        consent.status = ConsentStatus.EXPIRED
    return consent


def grant_for_application(
    db: Session,
    principal: Principal,
    application: Application,
    categories: list[str],
    purpose: str | None = None,
) -> Consent:
    if not principal.citizen_id or principal.citizen_id != application.citizen_id:
        raise ForbiddenError("Only the applicant can grant consent for this application")
    if application.status in TERMINAL_APPLICATION_STATUSES:
        raise InvalidStateError("Application is already closed")
    service = application.service
    requested = {c.upper() for c in categories}
    unknown = requested - VALID_CATEGORIES
    if unknown:
        raise DomainValidationError(f"Unknown data categories: {sorted(unknown)}")
    missing = set(service.required_categories) - requested
    if missing:
        raise DomainValidationError(
            "All required data categories must be allowed for this service",
            details={"missing_categories": sorted(missing)},
        )
    now = clock.now()
    # Supersede any earlier active consent for this application.
    for old in db.scalars(select(Consent).where(Consent.application_id == application.id, Consent.status == ConsentStatus.ACTIVE)):
        old.status = ConsentStatus.REVOKED
        old.revoked_at = now
        old.revocation_reason = "Superseded by a new consent"
    consent = Consent(
        id=uuid.uuid4(),
        citizen_id=application.citizen_id,
        requesting_department_id=application.department_id,
        service_id=service.id,
        application_id=application.id,
        data_categories=sorted(requested),
        purpose=purpose or service.consent_purpose,
        status=ConsentStatus.ACTIVE,
        granted_at=now,
        expires_at=now + timedelta(days=service.consent_validity_days or 180),
        granted_by=principal.username,
    )
    db.add(consent)
    application.consent_id = consent.id
    db.flush()
    outbox.emit(
        db, EventType.CONSENT_GRANTED, aggregate_type="consent", aggregate_id=str(consent.id),
        payload={
            "citizen_id": consent.citizen_id,
            "application_id": str(application.id),
            "application_number": application.application_number,
            "department": application.department.name,
            "categories": consent.data_categories,
        },
    )
    audit(
        "CITIZEN_GRANTED_CONSENT", "consent", str(consent.id),
        destination_system=application.department.name,
        details={"application": application.application_number, "categories": consent.data_categories, "purpose": consent.purpose, "expires_at": consent.expires_at.isoformat()},
    )
    return consent


def revoke(db: Session, principal: Principal, consent_id: uuid.UUID, reason: str | None = None) -> Consent:
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise NotFoundError("Consent not found")
    if consent.citizen_id != principal.citizen_id:
        raise ForbiddenError("You can only revoke your own consents")
    _expire_if_needed(consent)
    if consent.status != ConsentStatus.ACTIVE:
        raise InvalidStateError(f"Consent is already {consent.status}")
    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = clock.now()
    consent.revocation_reason = (reason or "Revoked by citizen")[:500]
    outbox.emit(
        db, EventType.CONSENT_REVOKED, aggregate_type="consent", aggregate_id=str(consent.id),
        payload={"citizen_id": consent.citizen_id, "department": consent.requesting_department.name, "categories": consent.data_categories},
    )
    audit("CITIZEN_REVOKED_CONSENT", "consent", str(consent.id), destination_system=consent.requesting_department.name,
          details={"categories": consent.data_categories, "reason": consent.revocation_reason})
    return consent


def find_active(db: Session, *, citizen_id: str, department_id: uuid.UUID, category: str, application_id: uuid.UUID | None = None) -> Consent | None:
    stmt = select(Consent).where(
        Consent.citizen_id == citizen_id,
        Consent.requesting_department_id == department_id,
        Consent.status == ConsentStatus.ACTIVE,
    )
    if application_id is not None:
        stmt = stmt.where(Consent.application_id == application_id)
    for consent in db.scalars(stmt.order_by(Consent.granted_at.desc())):
        _expire_if_needed(consent)
        if consent.status == ConsentStatus.ACTIVE and category in consent.data_categories:
            return consent
    return None


def has_consent_for(db: Session, *, citizen_id: str, department_id: uuid.UUID, categories: list[str], application_id: uuid.UUID) -> Consent | None:
    found = None
    for cat in categories:
        found = find_active(db, citizen_id=citizen_id, department_id=department_id, category=cat, application_id=application_id)
        if found is None:
            return None
    return found


def verify(
    db: Session,
    *,
    citizen_id: str,
    department_id: uuid.UUID,
    category: str,
    purpose: str | None,
    application_id: uuid.UUID | None = None,
    connector_key: str | None = None,
) -> Consent:
    """Gatekeeper for every data access. Raises ConsentRequiredError when not permitted."""
    ctx = get_context()
    consent = find_active(db, citizen_id=citizen_id, department_id=department_id, category=category, application_id=application_id)
    db.add(ConsentAccessLog(
        consent_id=consent.id if consent else None,
        citizen_id=citizen_id,
        data_category=category,
        accessor=ctx.actor,
        accessor_department_id=department_id,
        purpose=purpose,
        connector_key=connector_key,
        application_id=application_id,
        decision="ALLOWED" if consent else "DENIED",
        reason=None if consent else "No active consent covering this category",
        correlation_id=ctx.correlation_id,
    ))
    if consent is None:
        db.flush()
        audit("DATA_ACCESS_DENIED_NO_CONSENT", "citizen", citizen_id, status="DENIED", details={"category": category, "application_id": str(application_id) if application_id else None})
        raise ConsentRequiredError(f"Citizen consent required for {category} data", details={"category": category})
    return consent


def log_self_access(db: Session, citizen_id: str, category: str, connector_key: str) -> None:
    ctx = get_context()
    db.add(ConsentAccessLog(
        consent_id=None, citizen_id=citizen_id, data_category=category, accessor=ctx.actor,
        purpose="Citizen viewing own records", connector_key=connector_key, decision="ALLOWED",
        reason="SELF_ACCESS", correlation_id=ctx.correlation_id,
    ))


def list_for_citizen(db: Session, citizen_id: str, status: str | None = None) -> list[Consent]:
    stmt = select(Consent).where(Consent.citizen_id == citizen_id).order_by(Consent.granted_at.desc())
    if status:
        stmt = stmt.where(Consent.status == status)
    consents = list(db.scalars(stmt))
    for c in consents:
        _expire_if_needed(c)
    return consents


def access_logs(db: Session, consent_id: uuid.UUID) -> list[ConsentAccessLog]:
    return list(db.scalars(select(ConsentAccessLog).where(ConsentAccessLog.consent_id == consent_id).order_by(ConsentAccessLog.accessed_at.desc())))


def serialize(db: Session, consent: Consent, include_logs: bool = False) -> dict[str, Any]:
    app_number = None
    if consent.application_id:
        app = db.get(Application, consent.application_id)
        app_number = app.application_number if app else None
    data = {
        "consent_id": str(consent.id),
        "citizen_id": consent.citizen_id,
        "requesting_department": consent.requesting_department.name,
        "requesting_department_code": consent.requesting_department.code,
        "application_id": str(consent.application_id) if consent.application_id else None,
        "application_number": app_number,
        "data_categories": consent.data_categories,
        "purpose": consent.purpose,
        "status": consent.status,
        "timestamp": consent.granted_at,
        "expiry": consent.expires_at,
        "revoked_at": consent.revoked_at,
        "revocation_reason": consent.revocation_reason,
        "access_count": db.query(ConsentAccessLog).filter(ConsentAccessLog.consent_id == consent.id).count(),
    }
    if include_logs:
        data["access_logs"] = [
            {
                "accessed_at": log.accessed_at,
                "data_category": log.data_category,
                "accessor": log.accessor,
                "purpose": log.purpose,
                "connector": log.connector_key,
                "decision": log.decision,
            }
            for log in access_logs(db, consent.id)
        ]
    return data


def department_name(db: Session, department_id: uuid.UUID) -> str:
    dept = db.get(Department, department_id)
    return dept.name if dept else "Unknown"
