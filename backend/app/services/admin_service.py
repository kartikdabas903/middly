"""Aggregated statistics for the admin dashboard."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.redis import get_redis
from app.events.rabbit import DEAD_LETTER_QUEUE, publisher
from app.models import (
    Application,
    AuditLog,
    Connector,
    ConnectorCall,
    ConnectorHealth,
    Consent,
    ConsentAccessLog,
    DataQualityIssue,
    Department,
    Event,
    WorkflowInstance,
)
from app.services import connector_service


def _api_stats() -> dict[str, Any]:
    try:
        r = get_redis()
        req, fail, srv, cli, lat = r.mget("stats:api:requests", "stats:api:failures", "stats:api:server_errors", "stats:api:client_errors", "stats:api:latency_sum_ms")
        req_i = int(req or 0)
        return {
            "requests": req_i,
            "failures": int(fail or 0),
            "client_errors": int(cli or 0),
            "server_errors": int(srv or 0),
            "avg_latency_ms": round(float(lat or 0) / req_i, 1) if req_i else 0.0,
        }
    except Exception:
        return {"requests": 0, "failures": 0, "client_errors": 0, "server_errors": 0, "avg_latency_ms": 0.0}


def latest_health(db: Session) -> dict[Any, ConnectorHealth]:
    sub = select(ConnectorHealth.connector_id, func.max(ConnectorHealth.checked_at).label("mx")).group_by(ConnectorHealth.connector_id).subquery()
    rows = db.scalars(select(ConnectorHealth).join(sub, (ConnectorHealth.connector_id == sub.c.connector_id) & (ConnectorHealth.checked_at == sub.c.mx))).all()
    return {r.connector_id: r for r in rows}


def connector_cards(db: Session, include_fault: bool = False) -> list[dict[str, Any]]:
    health = latest_health(db)
    since = clock.now() - timedelta(hours=24)
    call_stats = {
        row.connector_id: row for row in db.execute(
            select(
                ConnectorCall.connector_id,
                func.count().label("calls"),
                func.sum(case((ConnectorCall.status == "SUCCESS", 1), else_=0)).label("ok"),
                func.avg(ConnectorCall.latency_ms).label("avg_latency"),
                func.max(ConnectorCall.created_at).label("last_call"),
            ).where(ConnectorCall.created_at >= since).group_by(ConnectorCall.connector_id)
        )
    }
    cards = []
    for c in db.scalars(select(Connector).order_by(Connector.name)).all():
        h = health.get(c.id)
        s = call_stats.get(c.id)
        calls = int(s.calls) if s else 0
        ok = int(s.ok or 0) if s else 0
        card = {
            "id": str(c.id), "key": c.key, "name": c.name, "system_name": c.system_name, "description": c.description,
            "department": c.department.name if c.department else None, "base_url": c.base_url, "auth_type": c.auth_type,
            "data_format": c.data_format, "data_categories": c.data_categories, "capabilities": c.capabilities,
            "enabled": c.enabled, "timeout_seconds": c.timeout_seconds, "max_retries": c.max_retries,
            "plugin_module": c.plugin_module, "version": c.version,
            "status": c.last_status, "last_checked_at": c.last_checked_at,
            "latency_ms": h.latency_ms if h else None, "message": h.message if h else None,
            "circuit_state": connector_service.circuit_state(c.key),
            "calls_24h": calls, "success_rate_24h": round(ok * 100 / calls, 1) if calls else None,
            "failures_24h": calls - ok, "avg_latency_ms_24h": round(float(s.avg_latency), 1) if s and s.avg_latency else None,
            "last_call_at": s.last_call if s else None,
        }
        if include_fault:
            card["fault_mode"] = connector_service.get_fault(c)
        cards.append(card)
    return cards


def overview(db: Session) -> dict[str, Any]:
    now = clock.now()
    by_dept = [
        {"department": name, "total": total, "approved": approved, "rejected": rejected, "pending": total - approved - rejected}
        for name, total, approved, rejected in db.execute(
            select(Department.name, func.count(Application.id),
                   func.sum(case((Application.status == "APPROVED", 1), else_=0)),
                   func.sum(case((Application.status == "REJECTED", 1), else_=0)))
            .join(Application, Application.department_id == Department.id).group_by(Department.name)
        )
    ]
    by_status = {s: n for s, n in db.execute(select(Application.status, func.count()).group_by(Application.status))}
    wf_status = {s: n for s, n in db.execute(select(WorkflowInstance.status, func.count()).group_by(WorkflowInstance.status))}
    ev_status = {s: n for s, n in db.execute(select(Event.status, func.count()).group_by(Event.status))}
    ev_types = [{"event_type": t, "count": n} for t, n in db.execute(select(Event.event_type, func.count()).group_by(Event.event_type).order_by(func.count().desc()))]
    consent_status = {s: n for s, n in db.execute(select(Consent.status, func.count()).group_by(Consent.status))}
    access = {d: n for d, n in db.execute(select(ConsentAccessLog.decision, func.count()).group_by(ConsentAccessLog.decision))}
    dq_open = [{"issue_type": t, "severity": sev, "count": n} for t, sev, n in db.execute(
        select(DataQualityIssue.issue_type, DataQualityIssue.severity, func.count()).where(DataQualityIssue.status == "OPEN")
        .group_by(DataQualityIssue.issue_type, DataQualityIssue.severity))]
    avg_processing = db.scalar(select(func.avg(Application.processing_seconds)).where(Application.processing_seconds.isnot(None)))
    calls_total, calls_failed, calls_avg = db.execute(select(
        func.count(), func.sum(case((ConnectorCall.status != "SUCCESS", 1), else_=0)), func.avg(ConnectorCall.latency_ms))).one()

    # Applications per day (last 14 days) for the trend chart.
    start = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    day = cast(Application.submitted_at, Date)
    per_day = {d.isoformat(): n for d, n in db.execute(
        select(day, func.count()).where(Application.submitted_at >= start).group_by(day))}
    trend = [{"date": (start + timedelta(days=i)).date().isoformat(), "applications": per_day.get((start + timedelta(days=i)).date().isoformat(), 0)} for i in range(14)]

    # Connector calls in the last hour, per connector.
    hour_ago = now - timedelta(hours=1)
    recent_calls = [
        {"connector": name, "success": int(ok or 0), "failure": int(total - (ok or 0))}
        for name, total, ok in db.execute(
            select(Connector.system_name, func.count(ConnectorCall.id), func.sum(case((ConnectorCall.status == "SUCCESS", 1), else_=0)))
            .join(ConnectorCall, ConnectorCall.connector_id == Connector.id).where(ConnectorCall.created_at >= hour_ago)
            .group_by(Connector.system_name))
    ]
    recent_audit = [
        {"id": a.id, "timestamp": a.timestamp, "actor": a.actor, "role": a.role, "action": a.action, "resource": a.resource,
         "resource_id": a.resource_id, "status": a.status, "source_system": a.source_system, "destination_system": a.destination_system}
        for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(8))
    ]
    return {
        "generated_at": now,
        "api": _api_stats(),
        "connectors": connector_cards(db),
        "connector_calls": {"total": calls_total or 0, "failed": int(calls_failed or 0), "avg_latency_ms": round(float(calls_avg or 0), 1)},
        "applications": {"total": sum(by_status.values()), "by_status": by_status, "by_department": by_dept, "trend": trend},
        "avg_processing_seconds": round(float(avg_processing), 1) if avg_processing else None,
        "workflows": wf_status,
        "events": {"by_status": ev_status, "by_type": ev_types, "dead_letter_depth": publisher.queue_depth(DEAD_LETTER_QUEUE)},
        "consents": {"by_status": consent_status, "access_allowed": access.get("ALLOWED", 0), "access_denied": access.get("DENIED", 0)},
        "data_quality": {"open_issues": dq_open, "open_total": sum(i["count"] for i in dq_open)},
        "recent_connector_calls": recent_calls,
        "recent_audit": recent_audit,
    }
