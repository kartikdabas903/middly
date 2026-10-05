from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.core.redis import get_redis
from app.db.session import get_engine
from app.events.rabbit import publisher

router = APIRouter(tags=["ops"])


@router.get("/health/live", include_in_schema=False)
def live() -> dict:
    return {"status": "UP"}


@router.get("/health", summary="Readiness: database, Redis and RabbitMQ")
def health() -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "UP"
    except Exception:
        checks["database"] = "DOWN"
    try:
        get_redis().ping()
        checks["redis"] = "UP"
    except Exception:
        checks["redis"] = "DOWN"
    checks["rabbitmq"] = "UP" if publisher.queue_depth("middly.dead-letter") is not None else "DOWN"
    ok = checks["database"] == "UP"
    status = "UP" if all(v == "UP" for v in checks.values()) else ("DEGRADED" if ok else "DOWN")
    return JSONResponse(status_code=200 if ok else 503, content={"status": status, "version": __version__, "checks": checks})
