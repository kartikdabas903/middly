"""Append-only, hash-chained audit trail.

Audit records are written in their own transaction so that failures (e.g.
SYSTEM_FETCH_FAILED) are recorded even when the business transaction rolls back.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import timezone
from typing import Any

from sqlalchemy import select, text

from app.core import clock
from app.core.context import get_context
from app.db.session import get_sessionmaker
from app.models import AuditLog

logger = logging.getLogger(__name__)

_CHAIN_LOCK = 72_001  # advisory lock id serialising the hash chain


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str | None, row: AuditLog | dict[str, Any]) -> str:
    get = (lambda k: row[k]) if isinstance(row, dict) else (lambda k: getattr(row, k))
    ts = get("timestamp").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    material = {
        "prev": prev_hash or "",
        "timestamp": ts,
        "actor": get("actor"),
        "role": get("role"),
        "action": get("action"),
        "resource": get("resource"),
        "resource_id": get("resource_id"),
        "source_system": get("source_system"),
        "destination_system": get("destination_system"),
        "status": get("status"),
        "ip_address": get("ip_address"),
        "correlation_id": get("correlation_id"),
        "details": get("details"),
    }
    return hashlib.sha256(_canonical(material).encode()).hexdigest()


def audit(
    action: str,
    resource: str,
    resource_id: str | None = None,
    *,
    status: str = "SUCCESS",
    source_system: str | None = None,
    destination_system: str | None = None,
    details: dict[str, Any] | None = None,
    actor: str | None = None,
    role: str | None = None,
) -> None:
    ctx = get_context()
    clean_details = json.loads(json.dumps(details or {}, default=str))
    db = get_sessionmaker()()
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK})
        prev = db.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1))
        row = {
            "timestamp": clock.now(),
            "actor": actor or ctx.actor,
            "role": role or ctx.role,
            "action": action,
            "resource": resource,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "source_system": source_system,
            "destination_system": destination_system,
            "status": status,
            "ip_address": ctx.client_ip,
            "correlation_id": ctx.correlation_id,
            "details": clean_details,
        }
        entry = AuditLog(**row, actor_id=ctx.actor_id, prev_hash=prev, hash=compute_hash(prev, row))
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to write audit record %s", action)
    finally:
        db.close()


def verify_chain(limit: int | None = None) -> dict[str, Any]:
    db = get_sessionmaker()()
    try:
        stmt = select(AuditLog).order_by(AuditLog.id)
        if limit:
            stmt = stmt.limit(limit)
        prev: str | None = None
        checked = 0
        for row in db.scalars(stmt).yield_per(500):
            expected = compute_hash(prev, row)
            if row.prev_hash != prev or row.hash != expected:
                return {"valid": False, "checked": checked, "broken_at_id": row.id}
            prev = row.hash
            checked += 1
        return {"valid": True, "checked": checked, "head_hash": prev}
    finally:
        db.close()
