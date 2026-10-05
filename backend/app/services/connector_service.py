"""Connector management: plugin sync, invocation with telemetry, health checks, demo faults."""
from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import get_context
from app.core.errors import NotFoundError, SourceUnavailableError
from app.core.metrics import CONNECTOR_FAILURE, CONNECTOR_LATENCY, CONNECTOR_SUCCESS, CONNECTOR_UP
from app.integration.errors import ConnectorError
from app.integration.registry import registry
from app.integration.sdk import BaseConnector, ConnectorConfig, HealthResult
from app.models import Connector, ConnectorCall, ConnectorHealth, Department
from app.models.enums import HealthStatus

logger = logging.getLogger(__name__)

_HEALTH_GAUGE = {"HEALTHY": 1.0, "DEGRADED": 0.5, "DOWN": 0.0}


def sync_registry(db: Session) -> list[Connector]:
    """Upsert one `connectors` row per discovered plugin. Admin-tuned settings are preserved."""
    settings = get_settings()
    departments = {d.code: d.id for d in db.scalars(select(Department)).all()}
    rows = []
    for key, cls in registry.all().items():
        row = db.scalar(select(Connector).where(Connector.key == key))
        if row is None:
            row = Connector(
                key=key,
                timeout_seconds=settings.connector_timeout_seconds,
                max_retries=settings.connector_max_retries,
                enabled=True,
            )
            db.add(row)
        row.name = cls.name
        row.system_name = cls.system_name
        row.description = cls.description
        row.department_id = departments.get(cls.department_code or "")
        row.base_url = cls.resolve_base_url()
        row.auth_type = cls.auth_type
        row.data_format = cls.data_format
        row.data_categories = list(cls.data_categories)
        row.capabilities = list(cls.capabilities)
        row.plugin_module = registry.module_of(key)
        row.version = cls.version
        rows.append(row)
    db.flush()
    return rows


def get_row(db: Session, key_or_id: str) -> Connector:
    try:
        cid = uuid.UUID(str(key_or_id))
        row = db.get(Connector, cid)
    except ValueError:
        row = db.scalar(select(Connector).where(Connector.key == key_or_id))
    if row is None:
        raise NotFoundError(f"Connector {key_or_id} not found")
    return row


def build_connector(row: Connector) -> BaseConnector:
    cls = registry.get_class(row.key)
    if cls is None:
        raise SourceUnavailableError(f"Connector plugin '{row.key}' is not installed")
    s = get_settings()
    config = ConnectorConfig(
        key=row.key,
        base_url=row.base_url,
        timeout_seconds=row.timeout_seconds,
        max_retries=row.max_retries,
        backoff_base_seconds=s.connector_backoff_base_seconds,
        circuit_failure_threshold=s.circuit_failure_threshold,
        circuit_open_seconds=s.circuit_open_seconds,
        credentials=cls.resolve_credentials(),
        correlation_id=get_context().correlation_id,
    )
    return cls(config)


def invoke(
    db: Session,
    key: str,
    operation: str,
    *args: Any,
    application_id: uuid.UUID | None = None,
    citizen_id: str | None = None,
) -> Any:
    """Invoke a connector operation and persist telemetry (connector_calls + metrics)."""
    row = get_row(db, key)
    if not row.enabled:
        raise SourceUnavailableError(f"{row.system_name} connector is disabled by an administrator")
    connector = build_connector(row)
    method = getattr(connector, operation)
    start = time.perf_counter()
    try:
        result = method(*args)
    except ConnectorError as exc:
        latency = (time.perf_counter() - start) * 1000
        status = "CIRCUIT_OPEN" if exc.reason == "CIRCUIT_OPEN" else "FAILURE"
        db.add(ConnectorCall(
            connector_id=row.id, operation=operation, status=status, http_status=exc.http_status or connector.last_call.http_status,
            latency_ms=round(latency, 1), attempts=max(1, connector.last_call.attempts), error=exc.message[:500],
            correlation_id=get_context().correlation_id, application_id=application_id, citizen_id=citizen_id,
        ))
        CONNECTOR_FAILURE.labels(key, operation, exc.reason).inc()
        CONNECTOR_LATENCY.labels(key, operation).observe(latency / 1000)
        raise
    latency = (time.perf_counter() - start) * 1000
    db.add(ConnectorCall(
        connector_id=row.id, operation=operation, status="SUCCESS", http_status=connector.last_call.http_status,
        latency_ms=round(latency, 1), attempts=max(1, connector.last_call.attempts),
        correlation_id=get_context().correlation_id, application_id=application_id, citizen_id=citizen_id,
    ))
    CONNECTOR_SUCCESS.labels(key, operation).inc()
    CONNECTOR_LATENCY.labels(key, operation).observe(latency / 1000)
    return result


def connector_meta(row: Connector) -> dict[str, Any]:
    return {"system_name": row.system_name, "key": row.key}


def _check(row_id: uuid.UUID, row: Connector) -> tuple[uuid.UUID, HealthResult, str]:
    try:
        connector = build_connector(row)
        result = connector.health_check()
        return row_id, result, connector.breaker.state
    except Exception as exc:
        return row_id, HealthResult(status=HealthStatus.DOWN, message=str(exc)), "UNKNOWN"


def run_health_checks(db: Session, keys: list[str] | None = None) -> list[dict[str, Any]]:
    rows = db.scalars(select(Connector).order_by(Connector.name)).all()
    if keys:
        rows = [r for r in rows if r.key in keys]
    with ThreadPoolExecutor(max_workers=max(1, len(rows))) as pool:
        results = list(pool.map(lambda r: _check(r.id, r), rows))
    by_id = {r.id: r for r in rows}
    out = []
    for row_id, result, circuit in results:
        row = by_id[row_id]
        status = result.status if row.enabled else HealthStatus.DOWN
        message = result.message if row.enabled else "Disabled by administrator"
        db.add(ConnectorHealth(connector_id=row.id, status=status, latency_ms=result.latency_ms, circuit_state=circuit, message=message))
        row.last_status = status
        row.last_checked_at = clock.now()
        CONNECTOR_UP.labels(row.key).set(_HEALTH_GAUGE.get(status, 0.0))
        out.append({"key": row.key, "status": status, "latency_ms": result.latency_ms, "circuit_state": circuit, "message": message})
    db.flush()
    return out


def circuit_state(key: str) -> str:
    from app.integration.circuit_breaker import CircuitBreaker

    s = get_settings()
    return CircuitBreaker(key, s.circuit_failure_threshold, s.circuit_open_seconds).state


# ----------------------------------------------------------------------------- demo fault injection

def set_fault(db: Session, key: str, mode: str) -> dict[str, Any]:
    row = get_row(db, key)
    resp = httpx.post(
        row.base_url.rstrip("/") + "/__demo/fault",
        json={"mode": mode},
        headers={"X-Admin-Key": get_settings().mock_admin_key},
        timeout=5.0,
    )
    resp.raise_for_status()
    return resp.json()


def get_fault(row: Connector) -> str | None:
    try:
        resp = httpx.get(row.base_url.rstrip("/") + "/__demo/fault", headers={"X-Admin-Key": get_settings().mock_admin_key}, timeout=2.0)
        return resp.json().get("mode") if resp.status_code == 200 else None
    except Exception:
        return None


def reset_mocks(db: Session) -> None:
    for row in db.scalars(select(Connector)).all():
        try:
            httpx.post(row.base_url.rstrip("/") + "/__demo/reset", headers={"X-Admin-Key": get_settings().mock_admin_key}, timeout=5.0)
        except Exception as exc:
            logger.warning("Could not reset mock %s: %s", row.key, exc)
