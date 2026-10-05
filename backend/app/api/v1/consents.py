from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import any_user, citizen_only
from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import Principal, Role
from app.db.session import get_db
from app.models import Consent
from app.repositories.queries import ConsentRepository
from app.schemas.requests import ConsentCreate, ConsentRevoke
from app.services import application_service, consent_service

router = APIRouter(prefix="/consents", tags=["consent"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Citizen grants explicit, purpose-bound consent")
def grant(body: ConsentCreate, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    app = application_service.load(db, str(body.application_id))
    consent = application_service.grant_consent(db, principal, app, [c.value for c in body.data_categories])
    db.commit()
    return consent_service.serialize(db, consent)


@router.get("", summary="Citizen: own consents (active + history). Platform admin: all consents")
def list_consents(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(ACTIVE|REVOKED|EXPIRED)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(any_user),
    db: Session = Depends(get_db),
) -> dict:
    if principal.citizen_id and Role.CITIZEN in principal.roles:
        items = consent_service.list_for_citizen(db, principal.citizen_id, status_filter)
        db.commit()
        return {"items": [consent_service.serialize(db, c) for c in items], "total": len(items), "limit": len(items), "offset": 0}
    if principal.is_platform_admin:
        rows, total = ConsentRepository.all(db, status=status_filter, limit=limit, offset=offset)
        return {"items": [consent_service.serialize(db, c) for c in rows], "total": total, "limit": limit, "offset": offset}
    raise ForbiddenError("Not allowed to list consents")


@router.get("/{consent_id}", summary="Consent details including every data access made under it")
def get_consent(consent_id: uuid.UUID, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise NotFoundError("Consent not found")
    if consent.citizen_id != principal.citizen_id and not principal.is_platform_admin:
        raise ForbiddenError("Not your consent")
    return consent_service.serialize(db, consent, include_logs=True)


@router.post("/{consent_id}/revoke", summary="Citizen revokes consent; further data access is blocked immediately")
def revoke(consent_id: uuid.UUID, body: ConsentRevoke | None = None, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    consent = consent_service.revoke(db, principal, consent_id, body.reason if body else None)
    db.commit()
    return consent_service.serialize(db, consent)
