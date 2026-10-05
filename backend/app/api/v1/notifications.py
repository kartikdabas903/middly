from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import citizen_only
from app.core import clock
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.db.session import get_db
from app.models import Notification
from app.repositories.queries import NotificationRepository

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", summary="Citizen notifications (delivered by the event-driven notification service)")
def list_notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    rows, total = NotificationRepository.for_citizen(db, principal.citizen_id or "", unread_only=unread_only, limit=limit, offset=offset)
    return {"items": [serializers.notification(n) for n in rows], "total": total, "limit": limit, "offset": offset,
            "unread": NotificationRepository.unread_count(db, principal.citizen_id or "")}


@router.get("/unread-count")
def unread_count(principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    return {"unread": NotificationRepository.unread_count(db, principal.citizen_id or "")}


@router.post("/{notification_id}/read")
def mark_read(notification_id: uuid.UUID, principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    n = db.get(Notification, notification_id)
    if n is None or n.citizen_id != principal.citizen_id:
        raise NotFoundError("Notification not found")
    n.read_at = n.read_at or clock.now()
    db.commit()
    return serializers.notification(n)


@router.post("/read-all")
def mark_all_read(principal: Principal = Depends(citizen_only), db: Session = Depends(get_db)) -> dict:
    result = db.execute(update(Notification).where(Notification.citizen_id == principal.citizen_id, Notification.read_at.is_(None))
                        .values(read_at=clock.now()))
    db.commit()
    return {"updated": result.rowcount}
