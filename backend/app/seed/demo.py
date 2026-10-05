"""Predictable demo dataset.

Historical scenarios are produced by running the *real* platform pipeline
(connectors, consent, workflow engine, events) against the mock department
systems, with the clock frozen at past dates. Nothing is inserted "by hand"
except reference data, so the seeded records look exactly like live ones.

    APP-2025-0001  Priya   Skill Development  withdrawn (consent auto-revoked)
    APP-2025-0002  Sneha   Skill Development  Employment Registry outage -> retry -> approved
    APP-2025-0003  Sneha*  Skill Development  failed eligibility (employed), duplicate-record DQ flag
    APP-2025-0004  Rahul   Grievance          resolved by the department system
    APP-2025-0005  Priya   Grievance          in progress at the department

The live demo then starts at APP-2026-0001.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, text

from app.core import clock
from app.core.config import get_settings
from app.core.context import RequestContext, reset_context, set_context, system_context
from app.core.redis import get_redis
from app.core.security import Principal, Role
from app.db.session import get_sessionmaker
from app.events.handlers import CONSUMERS
from app.events.rabbit import DEAD_LETTER_QUEUE, publisher
from app.models import Application, Connector, WorkflowInstance
from app.seed.reference import DEMO_USERS, seed_reference_data
from app.services import application_service, connector_service, data_access_service
from app.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)

TABLES = [
    "notifications", "consent_access_logs", "connector_calls", "connector_health", "data_quality_issues",
    "application_status_history", "workflow_steps", "workflow_instances", "events", "audit_logs",
    "consents", "applications", "application_sequences", "user_roles", "users", "services", "workflow_definitions",
    "connectors", "citizens", "departments", "roles",
]


def _principal(username: str) -> Principal:
    u = next(x for x in DEMO_USERS if x["username"] == username)
    return Principal(subject=u["id"], username=u["username"], roles={Role(r) for r in u["roles"]}, name=u["name"],
                     citizen_id=u.get("citizen_id"), department_code=u.get("department"))


def _citizen5() -> Principal:
    return Principal(subject=str(uuid.UUID(int=100005)), username="citizen5", roles={Role.CITIZEN}, name="Sneha Patil", citizen_id="100005")


@contextmanager
def acting_as(principal: Principal):
    ctx = RequestContext(correlation_id=f"seed-{uuid.uuid4()}", client_ip="10.0.0.10", actor=principal.username,
                         actor_id=principal.subject, role=principal.primary_role.value, department_code=principal.department_code)
    token = set_context(ctx)
    try:
        yield
    finally:
        reset_context(token)


def _at(text_ts: str) -> datetime:
    return datetime.fromisoformat(text_ts).replace(tzinfo=timezone.utc)


def _mock_admin(base_url: str, path: str, body: dict) -> None:
    httpx.post(base_url.rstrip("/") + path, json=body, headers={"X-Admin-Key": get_settings().mock_admin_key}, timeout=5).raise_for_status()


def _apply(principal: Principal, service: str, form: dict) -> uuid.UUID:
    with acting_as(principal), get_sessionmaker()() as db:
        app = application_service.create(db, principal, service, form)
        db.commit()
        return app.id


def _consent_and_process(principal: Principal, app_id: uuid.UUID, clk) -> None:
    with acting_as(principal), get_sessionmaker()() as db:
        app = db.get(Application, app_id)
        application_service.grant_consent(db, principal, app, app.service.required_categories)
        db.commit()
    clk.advance(seconds=20)
    with acting_as(principal), get_sessionmaker()() as db:
        app = db.get(Application, app_id)
        application_service.process(db, principal, app)
        db.commit()


def _process(principal: Principal | None, app_id: uuid.UUID) -> None:
    ctxmgr = acting_as(principal) if principal else system_context(actor="SYSTEM:auto-retry")
    with ctxmgr, get_sessionmaker()() as db:
        app = db.get(Application, app_id)
        if principal:
            application_service.process(db, principal, app)
        else:
            WorkflowEngine(db).advance(db.scalar(select(WorkflowInstance).where(WorkflowInstance.application_id == app_id)))
        db.commit()


def _officer(principal: Principal, app_id: uuid.UUID, action: str, remarks: str) -> None:
    with acting_as(principal), get_sessionmaker()() as db:
        app = db.get(Application, app_id)
        application_service.detail(db, principal, app)  # officer opens the application first
        application_service.officer_action(db, principal, app, action, remarks)
        db.commit()


def _connector_url(key: str) -> str:
    with get_sessionmaker()() as db:
        return db.scalar(select(Connector.base_url).where(Connector.key == key))


def run_historical_scenarios() -> None:
    priya, sneha, rahul = _principal("citizen2"), _principal("citizen4"), _principal("citizen1")
    officer, grievance_officer = _principal("officer1"), _principal("officer2")
    sneha_dup = _citizen5()

    # APP-2025-0001 — Priya applies, grants consent, then withdraws before verification completes.
    with frozen_time_at("2025-09-02T05:10:00") as clk:
        app1 = _apply(priya, "SKILL_DEV_SCHEME", {"preferred_trade": "ELECTRONICS_REPAIR", "preferred_district": "Nagpur", "training_mode": "CLASSROOM"})
        clk.advance(minutes=3)
        with acting_as(priya), get_sessionmaker()() as db:
            app = db.get(Application, app1)
            application_service.grant_consent(db, priya, app, app.service.required_categories)
            db.commit()
        clk.advance(minutes=4)
        with acting_as(priya), get_sessionmaker()() as db:
            application_service.withdraw(db, priya, db.get(Application, app1), "Applied for the wrong training district")
            db.commit()

    # APP-2025-0002 — Sneha: Employment Registry outage, automatic retry, officer approval.
    employment_url = _connector_url("employment")
    with frozen_time_at("2025-11-03T04:45:00") as clk:
        app2 = _apply(sneha, "SKILL_DEV_SCHEME", {"preferred_trade": "ELECTRICIAN", "preferred_district": "Kolhapur", "training_mode": "CLASSROOM"})
        clk.advance(minutes=2)
        _mock_admin(employment_url, "/__demo/fault", {"mode": "DOWN"})
        try:
            _consent_and_process(sneha, app2, clk)
        finally:
            _mock_admin(employment_url, "/__demo/fault", {"mode": "HEALTHY"})
        clk.advance(minutes=25)
        _process(None, app2)  # worker auto-retry succeeds once the registry is back
        clk.advance(hours=26)
        _officer(officer, app2, "APPROVE", "Identity, education and employment verified through registries. Approved for Electrician batch.")

    # APP-2025-0003 — duplicate Sneha record, salaried employment: fails DEMO eligibility.
    with frozen_time_at("2025-11-10T06:30:00") as clk:
        app3 = _apply(sneha_dup, "SKILL_DEV_SCHEME", {"preferred_trade": "RETAIL_SALES", "preferred_district": "Kolhapur", "training_mode": "HYBRID"})
        clk.advance(minutes=1)
        _consent_and_process(sneha_dup, app3, clk)

    # APP-2025-0004 — Rahul's grievance, resolved inside the department's own system.
    grievance_url = _connector_url("grievance")
    with frozen_time_at("2025-12-01T09:00:00") as clk:
        app4 = _apply(rahul, "GRIEVANCE_REDRESSAL", {"category": "SCHEME_BENEFIT", "subject": "Training completion certificate not received",
                                                     "description": "I completed a short-term training course in March but have not received the completion certificate."})
        clk.advance(days=3)
        with get_sessionmaker()() as db:
            ref = db.get(Application, app4).department_reference
        _mock_admin(grievance_url, f"/grievances/{ref}/status", {"state": "RESOLVED", "remarks": "Certificate dispatched to the registered address (demo)."})
        with system_context(actor="SYSTEM:status-sync"), get_sessionmaker()() as db:
            application_service.sync_external(db, None, db.get(Application, app4))
            db.commit()

    # APP-2025-0005 — Priya's grievance, still being worked on by the department.
    with frozen_time_at("2025-12-20T07:20:00"):
        _apply(priya, "GRIEVANCE_REDRESSAL", {"category": "RECORD_CORRECTION", "subject": "Middle name mismatch in education record",
                                              "description": "My education record shows my middle name but other records do not. Please align the records."})
    _ = grievance_officer


@contextmanager
def frozen_time_at(ts: str):
    with clock.frozen_time(_at(ts)) as clk:
        yield clk


def refresh_profiles() -> None:
    for username in ("citizen1", "citizen2", "citizen3"):
        p = _principal(username)
        with acting_as(p), get_sessionmaker()() as db:
            data_access_service.refresh_own_profile(db, p.citizen_id, p.username)
            db.commit()


def run_health_checks() -> None:
    with system_context(actor="SYSTEM:health-monitor"), get_sessionmaker()() as db:
        connector_service.run_health_checks(db)
        db.commit()


def seed() -> None:
    settings = get_settings()
    previous_mode = settings.event_dispatch_mode
    settings.event_dispatch_mode = "inline"
    try:
        with system_context(actor="SYSTEM:seeder"), get_sessionmaker()() as db:
            seed_reference_data(db)
        run_historical_scenarios()
        refresh_profiles()
        run_health_checks()
    finally:
        settings.event_dispatch_mode = previous_mode
    logger.info("Demo data seeded")


def is_seeded() -> bool:
    with get_sessionmaker()() as db:
        return db.scalar(select(Application.id).limit(1)) is not None


def reset() -> None:
    """Wipe platform data (keeps schema), reset mock systems, caches and queues."""
    with get_sessionmaker()() as db:
        try:
            connector_service.reset_mocks(db)
        except Exception as exc:  # connectors table may be empty
            logger.warning("Mock reset skipped: %s", exc)
        db.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
        db.commit()
    for url in ("http://mock-identity:8000", "http://mock-education:8000", "http://mock-employment:8000", "http://mock-skill:8000", "http://mock-grievance:8000"):
        try:
            _mock_admin(url, "/__demo/reset", {})
        except Exception:
            pass
    try:
        r = get_redis()
        for pattern in ("cb:*", "stats:*", "connector:token:*", "user:provisioned:*", "ratelimit:*"):
            for key in r.scan_iter(pattern):
                r.delete(key)
    except Exception as exc:
        logger.warning("Redis reset skipped: %s", exc)
    try:
        ch = publisher._ensure()
        for queue in [c.queue for c in CONSUMERS] + [DEAD_LETTER_QUEUE]:
            try:
                ch.queue_purge(queue)
            except Exception:
                ch = publisher._ensure()
    except Exception as exc:
        logger.warning("Queue purge skipped: %s", exc)
    logger.info("Demo environment reset")
