"""Fixed-window rate limiter backed by Redis (fails open if Redis is down)."""
from __future__ import annotations

import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def check_rate_limit(identity: str, limit_per_minute: int) -> tuple[bool, int]:
    """Returns (allowed, remaining)."""
    window = int(time.time() // 60)
    key = f"ratelimit:{identity}:{window}"
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 70)
        count, _ = pipe.execute()
    except Exception as exc:  # pragma: no cover - availability over strictness
        logger.warning("Rate limiter unavailable: %s", exc)
        return True, limit_per_minute
    remaining = max(0, limit_per_minute - int(count))
    return int(count) <= limit_per_minute, remaining
