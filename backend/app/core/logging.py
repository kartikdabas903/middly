from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.context import get_context


class JsonFormatter(logging.Formatter):
    """Structured JSON logs; every line carries the correlation id."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_context()
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": ctx.correlation_id,
            "actor": ctx.actor,
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("pika", "httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_extra(**fields) -> dict:
    return {"extra_fields": fields}
