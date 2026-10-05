from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import admin_roles, platform_admin
from app.core.security import Principal
from app.db.session import get_db
from app.repositories.queries import ConnectorRepository
from app.schemas.requests import ConnectorUpdate
from app.services import admin_service, connector_service
from app.services.audit_service import audit

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", summary="Registered department connectors with last health and 24h call statistics")
def list_connectors(_: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> list[dict]:
    return admin_service.connector_cards(db, include_fault=True)


@router.post("/health-check", summary="Run live health checks against every department system")
def check_all(_: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> list[dict]:
    results = connector_service.run_health_checks(db)
    db.commit()
    return results


@router.get("/{connector_id}", summary="Connector details")
def get_connector(connector_id: str, _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    row = connector_service.get_row(db, connector_id)
    return next(c for c in admin_service.connector_cards(db, include_fault=True) if c["key"] == row.key)


@router.get("/{connector_id}/health", summary="Live health check of one connector")
def connector_health(connector_id: str, _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    row = connector_service.get_row(db, connector_id)
    result = connector_service.run_health_checks(db, keys=[row.key])[0]
    db.commit()
    return result


@router.get("/{connector_id}/calls", summary="Recent calls made through this connector")
def connector_calls(connector_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    row = connector_service.get_row(db, connector_id)
    rows, total = ConnectorRepository.calls(db, row.id, limit, offset)
    return {"items": [serializers.connector_call(c) for c in rows], "total": total, "limit": limit, "offset": offset}


@router.patch("/{connector_id}", summary="Enable/disable a connector or tune its timeout/retries")
def update_connector(connector_id: str, body: ConnectorUpdate, _: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    row = connector_service.get_row(db, connector_id)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(row, k, v)
    db.commit()
    audit("ADMIN_UPDATED_CONNECTOR", "connector", row.key, details=changes)
    return next(c for c in admin_service.connector_cards(db) if c["key"] == row.key)
