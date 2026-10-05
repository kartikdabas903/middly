"""DEMO-mode controls (fault injection, reset). Disabled unless DEMO_MODE=true."""
from __future__ import annotations

import threading

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import platform_admin
from app.core.config import get_settings
from app.core.errors import ForbiddenError, InvalidStateError, NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.models import Application
from app.schemas.requests import FaultRequest
from app.services import application_service, connector_service
from app.services.audit_service import audit

router = APIRouter(prefix="/demo", tags=["demo"])

SCENARIOS = [
    {
        "id": 1,
        "title": "Successful cross-department application",
        "persona": "citizen1 (Rahul Sharma, Pune)",
        "steps": [
            "Login as citizen1 → Services → Skill Development Training Scheme → choose trade, district, mode.",
            "Review the consent request (Identity, Education, Employment) and click 'Allow & continue'.",
            "Watch the platform fetch from Identity Service, Education Registry and Employment Registry, normalise and validate.",
            "Eligibility passes (DEMO rules) → application APP-2026-0001 is forwarded to the department → Officer Review.",
            "Login as officer1 → Applications → open APP-2026-0001 → see consolidated profile with field provenance → Approve.",
            "APPLICATION_APPROVED is published to RabbitMQ → notification consumer stores the notification.",
            "Login as citizen1 → notification 'Application APP-2026-0001 approved.' → timeline fully green.",
            "Login as admin1 → dashboard shows connector calls, workflow, events, audit log and processing time.",
        ],
    },
    {
        "id": 2,
        "title": "Eligibility failure",
        "persona": "citizen3 (Amit Verma, Indore — outside Maharashtra, age 41, employed)",
        "steps": [
            "Login as citizen3 and apply for the Skill Development Training Scheme.",
            "Grant consent. Data is fetched and normalised; data quality flags a name mismatch (Verma/Varma) and a DOB conflict.",
            "Eligibility engine fails MAHARASHTRA_RESIDENT, AGE_RANGE and EMPLOYMENT_REQUIREMENT (DEMO rules).",
            "Workflow auto-rejects with reasons; APPLICATION_REJECTED event → citizen notified with the failed rules.",
        ],
    },
    {
        "id": 3,
        "title": "Department API failure and retry",
        "persona": "citizen2 (Priya Deshmukh, Nagpur)",
        "steps": [
            "Admin → Demo controls → set Employment Registry to DOWN (health card turns red).",
            "Login as citizen2, apply and grant consent. Identity and Education succeed; Employment times out after retries with backoff.",
            "Application shows 'Employment Registry ● Temporarily unavailable' and workflow state WAITING_FOR_SOURCE; nothing crashes.",
            "Repeated failures open the circuit breaker (fast-fail) — visible on the connector card.",
            "Admin restores the registry (HEALTHY). Citizen clicks Retry (or the worker auto-retries) → processing resumes to Officer Review.",
        ],
    },
]


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise ForbiddenError("Demo controls are disabled (DEMO_MODE=false)")


@router.get("/scenarios", summary="Guided demo scenarios")
def scenarios(_: Principal = Depends(platform_admin)) -> dict:
    return {"demo_mode": get_settings().demo_mode, "scenarios": SCENARIOS}


@router.post("/connectors/{key}/fault", summary="Inject a fault into a DEMO mock department system")
def set_fault(key: str, body: FaultRequest, _: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    _require_demo()
    result = connector_service.set_fault(db, key, body.mode)
    audit("ADMIN_INJECTED_FAULT", "connector", key, details={"mode": body.mode})
    health = connector_service.run_health_checks(db, keys=[key])
    db.commit()
    return {"connector": key, "fault": result, "health": health[0] if health else None}


@router.post("/grievances/{application_id}/resolve", summary="Simulate the department resolving a grievance in its own system")
def resolve_grievance(application_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    _require_demo()
    app = application_service.load(db, application_id)
    if app.service.code != "GRIEVANCE_REDRESSAL" or not app.department_reference:
        raise InvalidStateError("Not a registered grievance")
    row = connector_service.get_row(db, "grievance")
    httpx.post(f"{row.base_url}/grievances/{app.department_reference}/status", json={"state": "RESOLVED", "remarks": "Resolved by department (demo)"},
               headers={"X-Admin-Key": get_settings().mock_admin_key}, timeout=5).raise_for_status()
    application_service.sync_external(db, principal, app)
    db.commit()
    return {"application_number": app.application_number, "status": app.status}


_reset_lock = threading.Lock()


@router.post("/reset", summary="Reset the whole demo environment and re-seed predictable data")
def reset_demo(_: Principal = Depends(platform_admin)) -> dict:
    _require_demo()
    if not _reset_lock.acquire(blocking=False):
        raise InvalidStateError("A reset is already running")
    try:
        from app.seed import demo

        demo.reset()
        demo.seed()
    finally:
        _reset_lock.release()
    return {"reset": True}


@router.get("/applications/latest", summary="Latest application number (used by the demo guide)")
def latest(_: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    app = db.scalar(select(Application).order_by(Application.created_at.desc()).limit(1))
    if app is None:
        raise NotFoundError("No applications")
    return {"application_number": app.application_number, "status": app.status}
