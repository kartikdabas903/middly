from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import admin_roles
from app.core.security import Principal
from app.db.session import get_db
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", summary="Platform KPIs: API traffic, connectors, workflows, events, consent, data quality")
def overview(_: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    return admin_service.overview(db)
