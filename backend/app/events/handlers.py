"""Event consumers. The same functions run inside the RabbitMQ worker and, in
inline mode (seeding/tests), directly after commit.

    notification-dispatcher : business events -> NOTIFICATION_REQUESTED
    notification-service    : NOTIFICATION_REQUESTED -> stored in-app notification
                              (+ completes the workflow's notification step)
    department-sync         : decisions -> pushed to the department's own system
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import system_context
from app.core.metrics import EVENT_PROCESSING
from app.db.session import get_sessionmaker
from app.events import outbox
from app.events.types import EventType, routing_key_for
from app.integration.errors import ConnectorError, OperationNotSupportedError
from app.models import Application, Event, Notification, WorkflowInstance
from app.models.enums import EventStatus
from app.services import connector_service
from app.services.audit_service import audit

logger = logging.getLogger(__name__)


class RetryableHandlerError(Exception):
    """Raise to have the broker retry the message (and eventually dead-letter it)."""


# ----------------------------------------------------------------------------- notification templates

def _template(event_type: str, p: dict[str, Any]) -> dict[str, Any] | None:
    num = p.get("application_number", "")
    if event_type == EventType.APPLICATION_APPROVED:
        return {"title": "Application approved", "severity": "success",
                "message": f"Application {num} approved. {p.get('service', '')} — {p.get('department', '')}. "
                           f"{('Department reference: ' + p['department_reference'] + '.') if p.get('department_reference') else ''}".strip()}
    if event_type == EventType.APPLICATION_REJECTED:
        return {"title": "Application not approved", "severity": "error",
                "message": f"Application {num} was not approved. Reason: {p.get('reason') or 'Not specified'}"}
    if event_type == EventType.GRIEVANCE_RESOLVED:
        return {"title": "Grievance resolved", "severity": "success", "category": "GRIEVANCE",
                "message": f"Grievance {num} has been resolved by {p.get('department', 'the department')}. {p.get('reason') or ''}".strip()}
    if event_type == EventType.APPLICATION_SUBMITTED:
        return {"title": "Application verified and submitted", "severity": "info",
                "message": f"Application {num} was verified using department records and forwarded to {p.get('department')} for officer review."}
    if event_type == EventType.CLARIFICATION_REQUESTED:
        return {"title": "Clarification requested", "severity": "warning",
                "message": f"The officer reviewing {num} has asked: “{p.get('question')}”. Please respond from the application page."}
    if event_type == EventType.GRIEVANCE_CREATED:
        return {"title": "Grievance registered", "severity": "info", "category": "GRIEVANCE",
                "message": f"Your grievance {num} has been registered with {p.get('department')}."}
    if event_type == EventType.SOURCE_UNAVAILABLE:
        return {"title": "Verification delayed", "severity": "warning",
                "message": f"{p.get('system')} is temporarily unavailable, so {num} is waiting. We will retry automatically — no action needed."}
    if event_type == EventType.CONSENT_GRANTED:
        return {"title": "Consent recorded", "severity": "info", "category": "CONSENT",
                "message": f"You allowed {p.get('department')} to access your {', '.join(c.lower() for c in p.get('categories', []))} data for {num}."}
    if event_type == EventType.CONSENT_REVOKED:
        return {"title": "Consent revoked", "severity": "warning", "category": "CONSENT",
                "message": f"Your consent for {p.get('department')} has been revoked. They can no longer access your data."}
    return None


def handle_dispatch(db: Session, message: dict[str, Any]) -> None:
    payload = message["payload"]
    tpl = _template(message["event_type"], payload)
    if tpl is None or not payload.get("citizen_id"):
        return
    outbox.emit(db, EventType.NOTIFICATION_REQUESTED, aggregate_type=message["aggregate_type"], aggregate_id=message["aggregate_id"], payload={
        "source_event_id": message["event_id"],
        "source_event_type": message["event_type"],
        "citizen_id": payload["citizen_id"],
        "application_id": payload.get("application_id"),
        "title": tpl["title"],
        "message": tpl["message"],
        "severity": tpl["severity"],
        "category": tpl.get("category", "APPLICATION"),
        "complete_step": payload.get("notify_step"),
    })


def handle_notification(db: Session, message: dict[str, Any]) -> None:
    from app.workflow.engine import WorkflowEngine

    p = message["payload"]
    source_event = uuid.UUID(p["source_event_id"])
    if db.scalar(select(Notification.id).where(Notification.event_id == source_event)):
        return  # idempotent: already delivered
    app_id = uuid.UUID(p["application_id"]) if p.get("application_id") else None
    db.add(Notification(
        citizen_id=p["citizen_id"], title=p["title"], message=p["message"], severity=p.get("severity", "info"),
        category=p.get("category", "APPLICATION"), application_id=app_id, event_id=source_event,
    ))
    db.flush()
    audit("NOTIFICATION_SENT", "notification", p["citizen_id"], details={"title": p["title"], "source_event": p["source_event_type"]})
    if p.get("complete_step") and app_id:
        instance = db.scalar(select(WorkflowInstance).where(WorkflowInstance.application_id == app_id))
        if instance:
            WorkflowEngine(db).complete_event_step(instance, p["complete_step"], {
                "notification_title": p["title"], "delivered_at": clock.now().isoformat(), "channel": "IN_APP"})


def handle_department_sync(db: Session, message: dict[str, Any]) -> None:
    p = message["payload"]
    app = db.get(Application, uuid.UUID(p["application_id"]))
    if app is None or not app.department_reference or not app.service.department_connector_key:
        return
    if app.service.workflow_code == "GRIEVANCE_REDRESSAL":
        return  # grievance decisions originate in the department system
    key = app.service.department_connector_key
    try:
        result = connector_service.invoke(db, key, "update_application", app.department_reference,
                                          {"decision": p["decision"], "remarks": p.get("reason"), "decided_by": p.get("decided_by")},
                                          application_id=app.id)
    except OperationNotSupportedError:
        return
    except ConnectorError as exc:
        db.commit()  # keep the connector_calls telemetry row
        raise RetryableHandlerError(f"Department sync failed: {exc.message}") from exc
    audit("SYSTEM_SYNCED_DECISION", "application", str(app.id), source_system="Middly Platform",
          destination_system=app.department.name, details={"department_reference": app.department_reference, "department_status": result.get("status"),
                                                           "batch_code": result.get("batch_code")})
    snapshot = dict(app.profile_snapshot or {})
    snapshot["department_record"] = result
    app.profile_snapshot = snapshot


def handle_event_log(db: Session, message: dict[str, Any]) -> None:
    """Analytics/event-log consumer: subscribes to every event (marks delivery for observability)."""


ALL_EVENTS = ("*",)


@dataclass(frozen=True)
class Consumer:
    name: str
    queue: str
    event_types: tuple[str, ...]
    handler: Callable[[Session, dict[str, Any]], None]

    @property
    def routing_keys(self) -> list[str]:
        if self.event_types == ALL_EVENTS:
            return ["#"]
        return [routing_key_for(t) for t in self.event_types]

    def handles(self, event_type: str) -> bool:
        return self.event_types == ALL_EVENTS or event_type in self.event_types


CONSUMERS: list[Consumer] = [
    Consumer("event-log", "middly.event-log", ALL_EVENTS, handle_event_log),
    Consumer(
        "notification-dispatcher", "middly.notification-dispatcher",
        (EventType.APPLICATION_APPROVED, EventType.APPLICATION_REJECTED, EventType.APPLICATION_SUBMITTED, EventType.CLARIFICATION_REQUESTED,
         EventType.GRIEVANCE_CREATED, EventType.GRIEVANCE_RESOLVED, EventType.SOURCE_UNAVAILABLE, EventType.CONSENT_GRANTED, EventType.CONSENT_REVOKED),
        handle_dispatch,
    ),
    Consumer("notification-service", "middly.notification-service", (EventType.NOTIFICATION_REQUESTED,), handle_notification),
    Consumer("department-sync", "middly.department-sync", (EventType.APPLICATION_APPROVED, EventType.APPLICATION_REJECTED), handle_department_sync),
]


def consumers_for(event_type: str) -> list[Consumer]:
    return [c for c in CONSUMERS if c.handles(event_type)]


def process_message(consumer: Consumer, message: dict[str, Any]) -> None:
    """Run one consumer for one message in its own transaction and track delivery on the event row."""
    event_id = uuid.UUID(message["event_id"])
    with system_context(correlation_id=message.get("correlation_id"), actor=f"SYSTEM:{consumer.name}"):
        db = get_sessionmaker()()
        try:
            evt = db.get(Event, event_id)
            if evt is not None and consumer.name in (evt.processed_by or []):
                EVENT_PROCESSING.labels(message["event_type"], consumer.name, "duplicate").inc()
                return
            consumer.handler(db, message)
            if evt is not None:
                evt.processed_by = sorted(set(evt.processed_by or []) | {consumer.name})
                evt.status = EventStatus.PROCESSED
                evt.processed_at = clock.now()
                evt.last_error = None
            db.commit()
            EVENT_PROCESSING.labels(message["event_type"], consumer.name, "success").inc()
        except IntegrityError:
            db.rollback()
            EVENT_PROCESSING.labels(message["event_type"], consumer.name, "duplicate").inc()
        except Exception as exc:
            db.rollback()
            EVENT_PROCESSING.labels(message["event_type"], consumer.name, "failure").inc()
            mark_event(event_id, EventStatus.FAILED, f"{consumer.name}: {exc}")
            raise
        finally:
            db.close()


def mark_event(event_id: uuid.UUID, status: str, error: str | None = None) -> None:
    db = get_sessionmaker()()
    try:
        evt = db.get(Event, event_id)
        if evt:
            evt.status = status
            evt.attempts += 1
            evt.last_error = (error or "")[:500] or evt.last_error
            db.commit()
    finally:
        db.close()


def dispatch_inline(event_id: uuid.UUID) -> None:
    db = get_sessionmaker()()
    try:
        evt = db.get(Event, event_id)
        if evt is None:
            return
        message = outbox.to_message(evt)
        evt.status = EventStatus.PUBLISHED
        evt.published_at = clock.now()
        db.commit()
    finally:
        db.close()
    targets = consumers_for(message["event_type"])
    if not targets:
        mark_event(event_id, EventStatus.PROCESSED)
    for consumer in targets:
        try:
            process_message(consumer, message)
        except Exception:
            logger.exception("Inline consumer %s failed for %s", consumer.name, message["event_type"])
