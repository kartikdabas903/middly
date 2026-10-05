from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import admin_roles, platform_admin
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.events.handlers import CONSUMERS
from app.events.outbox import dispatch_events
from app.events.rabbit import DEAD_LETTER_QUEUE, publisher
from app.models import Event
from app.models.enums import EventStatus
from app.repositories.queries import EventRepository
from app.services.audit_service import audit

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", summary="Domain events (outbox + delivery status)")
def list_events(event_type: str | None = Query(None, max_length=60), status: str | None = Query(None, max_length=20),
                aggregate_id: str | None = Query(None, max_length=80), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                _: Principal = Depends(admin_roles), db: Session = Depends(get_db)) -> dict:
    rows, total = EventRepository.search(db, event_type=event_type, status=status, aggregate_id=aggregate_id, limit=limit, offset=offset)
    return {"items": [serializers.event(e) for e in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/topology", summary="RabbitMQ consumers, bindings and queue depths")
def topology(_: Principal = Depends(admin_roles)) -> dict:
    return {
        "exchange": "middly.events",
        "dead_letter_queue": {"name": DEAD_LETTER_QUEUE, "depth": publisher.queue_depth(DEAD_LETTER_QUEUE)},
        "consumers": [
            {"name": c.name, "queue": c.queue, "routing_keys": c.routing_keys, "depth": publisher.queue_depth(c.queue)}
            for c in CONSUMERS
        ],
    }


@router.post("/{event_id}/replay", summary="Re-publish an event (e.g. after fixing a dead-lettered failure)")
def replay(event_id: uuid.UUID, _: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    evt = db.get(Event, event_id)
    if evt is None:
        raise NotFoundError("Event not found")
    evt.status = EventStatus.PENDING
    evt.processed_by = []
    db.commit()
    dispatch_events([evt.id])
    audit("ADMIN_REPLAYED_EVENT", "event", str(evt.id), details={"event_type": evt.event_type})
    db.refresh(evt)
    return serializers.event(evt)
