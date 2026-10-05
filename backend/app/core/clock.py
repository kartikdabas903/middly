"""Injectable clock.

All timestamps written by the platform go through `now()`. The demo seeder uses
`frozen_time()` to create historical records with realistic dates without
mutating append-only tables afterwards.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Iterator

_override: ContextVar[list[datetime] | None] = ContextVar("middly_clock", default=None)


def now() -> datetime:
    box = _override.get()
    if box:
        return box[0]
    return datetime.now(timezone.utc)


@contextmanager
def frozen_time(at: datetime) -> Iterator["_ClockHandle"]:
    box = [at]
    token = _override.set(box)
    try:
        yield _ClockHandle(box)
    finally:
        _override.reset(token)


class _ClockHandle:
    def __init__(self, box: list[datetime]):
        self._box = box

    def advance(self, **kwargs) -> datetime:
        self._box[0] = self._box[0] + timedelta(**kwargs)
        return self._box[0]

    @property
    def current(self) -> datetime:
        return self._box[0]
