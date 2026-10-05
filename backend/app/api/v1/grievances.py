from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import any_user, citizen_only
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.schemas.requests import GrievanceCreate
from app.services import application_service as svc

router = APIRouter(prefix="/grievances", tags=["grievances"])

GRIEVANCE_SERVICE = "GRIEVANCE_REDRESSAL"


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register a grievance with the department system (tracked like an application)")
def create_grievance(body: GrievanceCreate, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    app = svc.create(db, principal, GRIEVANCE_SERVICE, body.model_dump())
    db.commit()
    db.expire_all()
    return svc.detail(db, principal, svc.load(db, str(app.id)))


@router.get("/{grievance_id}", summary="Grievance status (synchronised from the department system)")
def get_grievance(grievance_id: str, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    app = svc.load(db, grievance_id)
    if app.service.code != GRIEVANCE_SERVICE:
        raise NotFoundError("Grievance not found")
    svc.sync_external(db, principal, app)
    db.commit()
    db.expire_all()
    return svc.detail(db, principal, svc.load(db, grievance_id))
