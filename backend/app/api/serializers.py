"""Model -> JSON shapes shared by routers."""
from __future__ import annotations

from typing import Any

from app.models import AuditLog, ConnectorCall, DataQualityIssue, Event, Notification, WorkflowInstance


def audit_log(a: AuditLog) -> dict[str, Any]:
    return {
        "id": a.id, "timestamp": a.timestamp, "actor": a.actor, "role": a.role, "action": a.action, "resource": a.resource,
        "resource_id": a.resource_id, "source_system": a.source_system, "destination_system": a.destination_system,
        "status": a.status, "ip_address": a.ip_address, "correlation_id": a.correlation_id, "details": a.details, "hash": a.hash,
    }


def event(e: Event) -> dict[str, Any]:
    return {
        "id": str(e.id), "event_type": e.event_type, "routing_key": e.routing_key, "aggregate_type": e.aggregate_type,
        "aggregate_id": e.aggregate_id, "payload": e.payload, "status": e.status, "correlation_id": e.correlation_id,
        "attempts": e.attempts, "last_error": e.last_error, "processed_by": e.processed_by,
        "created_at": e.created_at, "published_at": e.published_at, "processed_at": e.processed_at,
    }


def notification(n: Notification) -> dict[str, Any]:
    return {
        "id": str(n.id), "title": n.title, "message": n.message, "category": n.category, "severity": n.severity,
        "application_id": str(n.application_id) if n.application_id else None, "read": n.read_at is not None,
        "read_at": n.read_at, "created_at": n.created_at, "channel": n.channel,
    }


def dq_issue(i: DataQualityIssue) -> dict[str, Any]:
    return {
        "id": str(i.id), "citizen_id": i.citizen_id, "application_id": str(i.application_id) if i.application_id else None,
        "source_system": i.source_system, "issue_type": i.issue_type, "severity": i.severity, "field": i.field,
        "message": i.message, "details": i.details, "status": i.status, "detected_at": i.detected_at,
        "resolved_at": i.resolved_at, "resolved_by": i.resolved_by,
    }


def workflow_instance(w: WorkflowInstance, application_number: str | None = None, include_steps: bool = True) -> dict[str, Any]:
    data = {
        "id": str(w.id), "application_id": str(w.application_id), "application_number": application_number,
        "workflow": w.definition.code, "workflow_name": w.definition.name, "version": w.definition.version,
        "status": w.status, "current_step": w.current_step_key, "last_error": w.last_error,
        "started_at": w.started_at, "completed_at": w.completed_at, "updated_at": w.updated_at,
        "progress": {"completed": sum(1 for s in w.steps if s.status in ("COMPLETED", "SKIPPED")), "total": len(w.steps)},
    }
    if include_steps:
        data["steps"] = [
            {"key": s.step_key, "type": s.step_type, "label": s.label, "sequence": s.sequence, "status": s.status,
             "attempts": s.attempts, "started_at": s.started_at, "completed_at": s.completed_at, "error": s.error,
             "output": _redact(s.output)}
            for s in w.steps
        ]
    return data


def _redact(output: dict[str, Any] | None) -> dict[str, Any]:
    """Workflow monitoring must not leak personal data: drop canonical payloads."""
    if not output:
        return {}
    return {k: v for k, v in output.items() if k not in {"canonical", "warnings", "history"}}


def connector_call(c: ConnectorCall) -> dict[str, Any]:
    return {
        "id": str(c.id), "operation": c.operation, "status": c.status, "http_status": c.http_status,
        "latency_ms": c.latency_ms, "attempts": c.attempts, "error": c.error, "correlation_id": c.correlation_id,
        "application_id": str(c.application_id) if c.application_id else None, "created_at": c.created_at,
    }
