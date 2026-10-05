"""Request-scoped context (correlation id, actor, client ip) carried via contextvars.

The same context is used by HTTP requests, the event worker and the seeder so
audit records and connector calls are always attributable.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class RequestContext:
    correlation_id: str = field(default_factory=lambda: f"sys-{uuid.uuid4()}")
    client_ip: str | None = None
    actor: str = "SYSTEM"
    actor_id: str | None = None
    role: str = "SYSTEM"
    department_code: str | None = None


_ctx: ContextVar[RequestContext | None] = ContextVar("middly_request_ctx", default=None)


def get_context() -> RequestContext:
    ctx = _ctx.get()
    if ctx is None:
        ctx = RequestContext()
        _ctx.set(ctx)
    return ctx


def set_context(ctx: RequestContext):
    return _ctx.set(ctx)


def reset_context(token) -> None:
    _ctx.reset(token)


@contextmanager
def system_context(correlation_id: str | None = None, actor: str = "SYSTEM") -> Iterator[RequestContext]:
    ctx = RequestContext(correlation_id=correlation_id or f"sys-{uuid.uuid4()}", actor=actor, role="SYSTEM")
    token = _ctx.set(ctx)
    try:
        yield ctx
    finally:
        _ctx.reset(token)
