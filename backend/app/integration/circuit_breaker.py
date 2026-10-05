"""Redis-backed circuit breaker shared by the API and the worker processes.

CLOSED    -> calls flow; consecutive failures are counted.
OPEN      -> calls fail fast until `open_seconds` elapse.
HALF_OPEN -> one trial call is allowed; success closes, failure re-opens.
"""
from __future__ import annotations

import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, open_seconds: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._k_fail = f"cb:{name}:failures"
        self._k_open = f"cb:{name}:opened_until"
        self._local = {"failures": 0, "opened_until": 0.0}

    def _get(self):
        try:
            r = get_redis()
            failures, opened = r.mget(self._k_fail, self._k_open)
            return int(failures or 0), float(opened or 0)
        except Exception:  # Redis down: degrade to process-local state
            return self._local["failures"], self._local["opened_until"]

    @property
    def state(self) -> str:
        _, opened_until = self._get()
        if not opened_until:
            return "CLOSED"
        return "OPEN" if time.time() < opened_until else "HALF_OPEN"

    def retry_after(self) -> int:
        _, opened_until = self._get()
        return max(0, int(opened_until - time.time()))

    def allow(self) -> bool:
        return self.state != "OPEN"

    def record_success(self) -> None:
        self._local.update(failures=0, opened_until=0.0)
        try:
            get_redis().delete(self._k_fail, self._k_open)
        except Exception:
            pass

    def record_failure(self) -> None:
        state_before = self.state
        try:
            r = get_redis()
            failures = r.incr(self._k_fail)
            r.expire(self._k_fail, 300)
        except Exception:
            self._local["failures"] += 1
            failures = self._local["failures"]
        if failures >= self.failure_threshold or state_before == "HALF_OPEN":
            opened_until = time.time() + self.open_seconds
            self._local["opened_until"] = opened_until
            try:
                get_redis().set(self._k_open, opened_until, ex=self.open_seconds * 10)
            except Exception:
                pass
            logger.warning("Circuit opened for connector %s", self.name)

    def reset(self) -> None:
        self.record_success()
