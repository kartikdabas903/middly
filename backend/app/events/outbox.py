"""Transactional outbox.

`emit()` writes the event row in the caller's transaction. After that
transaction commits, the events are published to RabbitMQ (or, in inline mode,
dispatched to the in-process consumer handlers). The worker's relay re-publishes
anything left PENDING, so no event is lost if the broker is briefly down.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import get_context
from app.core.metrics import EVENTS_PUBLISHED
from app.events.types import routing_key_for
from app.models import Event
from app.models.enums import EventStatus

logger = logging.getLogger(__name__)

_OUTBOX_KEY = "middly_outbox"


def emit(db: Session, event_type: str, *, aggregate_type: str, aggregate_id: str, payload: dict[str, Any] | None = None) -> Event:
    ctx = get_context()
    evt = Event(
        id=uuid.uuid4(),
        event_type=str(event_type),
        routing_key=routing_key_for(str(event_type)),
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload or {},
        status=EventStatus.PENDING,
        correlation_id=ctx.correlation_id,
        processed_by=[],
    )
    db.add(evt)
    db.info.setdefault(_OUTBOX_KEY, []).append(evt.id)
    return evt


def to_message(evt: Event) -> dict[str, Any]:
    return {
        "event_id": str(evt.id),
        "event_type": evt.event_type,
        "occurred_at": evt.created_at.isoformat() if evt.created_at else None,
        "correlation_id": evt.correlation_id,
        "aggregate_type": evt.aggregate_type,
        "aggregate_id": evt.aggregate_id,
        "payload": evt.payload,
    }


@sa_event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    ids = session.info.pop(_OUTBOX_KEY, None)
    if ids:
        dispatch_events(ids)


@sa_event.listens_for(Session, "after_soft_rollback")
def _after_rollback(session: Session, previous_transaction) -> None:
    session.info.pop(_OUTBOX_KEY, None)


def dispatch_events(event_ids: list[uuid.UUID]) -> None:
    mode = get_settings().event_dispatch_mode
    if mode == "inline":
        from app.events.handlers import dispatch_inline

        for event_id in event_ids:
            dispatch_inline(event_id)
        return
    publish_events(event_ids)


def publish_events(event_ids: list[uuid.UUID]) -> int:
    from app.db.session import get_sessionmaker
    from app.events.rabbit import publisher

    published = 0
    db = get_sessionmaker()()
    try:
        events = db.scalars(select(Event).where(Event.id.in_(event_ids), Event.status == EventStatus.PENDING)).all()
        for evt in events:
            try:
                publisher.publish(evt.routing_key, to_message(evt), message_id=str(evt.id), correlation_id=evt.correlation_id)
                evt.status = EventStatus.PUBLISHED
                evt.published_at = clock.now()
                evt.attempts += 1
                EVENTS_PUBLISHED.labels(evt.event_type).inc()
                published += 1
            except Exception as exc:
                evt.attempts += 1
                evt.last_error = f"publish failed: {exc}"[:500]
                logger.warning("Event %s left in outbox: %s", evt.id, exc)
            # Commit per event so a crash never re-publishes already-confirmed events.
            db.commit()
    finally:
        db.close()
    return published


def relay_pending(max_age_seconds: int = 3, limit: int = 200) -> int:
    """Re-publish events stuck in PENDING (broker outage, crash after commit)."""
    from app.db.session import get_sessionmaker

    cutoff = clock.now() - timedelta(seconds=max_age_seconds)
    db = get_sessionmaker()()
    try:
        ids = db.scalars(
            select(Event.id).where(Event.status == EventStatus.PENDING, Event.created_at < cutoff).order_by(Event.created_at).limit(limit)
        ).all()
    finally:
        db.close()
    return publish_events(list(ids)) if ids else 0
