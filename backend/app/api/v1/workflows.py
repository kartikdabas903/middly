from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import admin_roles, any_user
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.models import Application
from app.repositories.queries import WorkflowRepository
from app.services.application_service import authorize_view

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/definitions", summary="Configured workflow definitions (JSON)")
def definitions(_: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": str(d.id), "code": d.code, "version": d.version, "name": d.name, "description": d.description,
         "is_active": d.is_active, "definition": d.definition, "created_at": d.created_at}
        for d in WorkflowRepository.definitions(db)
    ]


@router.get("/definitions/{code}", summary="Latest version of a workflow definition")
def definition(code: str, _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    d = WorkflowRepository.definition(db, code)
    if d is None:
        raise NotFoundError("Workflow definition not found")
    return {"id": str(d.id), "code": d.code, "version": d.version, "name": d.name, "definition": d.definition}


@router.get("", summary="Workflow instances (monitoring)")
def instances(status: str | None = Query(None, max_length=40), definition: str | None = Query(None, max_length=80),
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
              _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    rows, total = WorkflowRepository.instances(db, status=status, definition=definition, limit=limit, offset=offset)
    numbers = WorkflowRepository.application_numbers(db, [r.application_id for r in rows])
    return {"items": [serializers.workflow_instance(r, numbers.get(r.application_id), include_steps=False) for r in rows],
            "total": total, "limit": limit, "offset": offset}


@router.get("/{instance_id}", summary="Workflow instance with persisted step states")
def instance(instance_id: uuid.UUID, principal: Principal = Depends(any_user), db: Session = Depends(get_db)) -> dict:
    wf = WorkflowRepository.instance(db, instance_id)
    if wf is None:
        raise NotFoundError("Workflow instance not found")
    app = db.get(Application, wf.application_id)
    authorize_view(principal, app)
    return serializers.workflow_instance(wf, app.application_number)
