"""Refreshes business gauges (applications, workflows, connector health) on each Prometheus scrape."""
from __future__ import annotations

import logging
import time

from sqlalchemy import func, select

from app.core.metrics import APPLICATIONS_BY_STATUS, CONNECTOR_UP, WORKFLOW_INSTANCES_BY_STATUS
from app.db.session import get_sessionmaker
from app.models import Application, Connector, Department, WorkflowInstance

logger = logging.getLogger(__name__)
_last = 0.0
_HEALTH = {"HEALTHY": 1.0, "DEGRADED": 0.5, "DOWN": 0.0}


def refresh_business_gauges(min_interval: float = 5.0) -> None:
    global _last
    if time.monotonic() - _last < min_interval:
        return
    _last = time.monotonic()
    try:
        with get_sessionmaker()() as db:
            APPLICATIONS_BY_STATUS.clear()
            for status, dept, n in db.execute(
                select(Application.status, Department.code, func.count()).join(Department, Department.id == Application.department_id)
                .group_by(Application.status, Department.code)
            ):
                APPLICATIONS_BY_STATUS.labels(status, dept).set(n)
            WORKFLOW_INSTANCES_BY_STATUS.clear()
            for status, n in db.execute(select(WorkflowInstance.status, func.count()).group_by(WorkflowInstance.status)):
                WORKFLOW_INSTANCES_BY_STATUS.labels(status).set(n)
            for key, status in db.execute(select(Connector.key, Connector.last_status)):
                CONNECTOR_UP.labels(key).set(_HEALTH.get(status, 0.0))
    except Exception as exc:  # pragma: no cover
        logger.warning("Business gauge refresh failed: %s", exc)
