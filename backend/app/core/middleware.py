"""HTTP middleware: correlation ids, security headers, rate limiting, metrics, access log."""
from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.context import RequestContext, reset_context, set_context
from app.core.logging import log_extra
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis

logger = logging.getLogger("middly.access")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_UNMETERED = {"/health", "/health/live", "/metrics"}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        correlation_id = incoming if incoming and _SAFE_ID.match(incoming) else str(uuid.uuid4())
        ctx = RequestContext(correlation_id=correlation_id, client_ip=_client_ip(request), actor="ANONYMOUS", role="ANONYMOUS")
        token = set_context(ctx)
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        status = 500
        try:
            if request.url.path.startswith("/api/") and request.method != "OPTIONS":
                identity = _rate_identity(request, ctx.client_ip)
                allowed, remaining = check_rate_limit(identity, get_settings().rate_limit_per_minute)
                if not allowed:
                    status = 429
                    return JSONResponse(
                        status_code=429,
                        content={"error": {"code": "RATE_LIMITED", "message": "Too many requests", "correlation_id": correlation_id}},
                        headers={"X-Request-ID": correlation_id, "Retry-After": "60"},
                    )
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = request.url.path
            if path not in _UNMETERED:
                route = _route_template(request)
                REQUEST_COUNT.labels(request.method, route, str(status)).inc()
                REQUEST_LATENCY.labels(request.method, route).observe(elapsed)
                _record_api_stats(path, status, elapsed)
                logger.info(
                    "%s %s -> %s",
                    request.method,
                    path,
                    status,
                    extra=log_extra(method=request.method, path=path, status=status, duration_ms=round(elapsed * 1000, 1), client_ip=ctx.client_ip),
                )
            reset_context(token)


def _rate_identity(request: Request, ip: str | None) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 40:
        # Key on the token tail: stable per session, never stored in full.
        return "tok:" + auth[-24:]
    return f"ip:{ip or 'unknown'}"


def _record_api_stats(path: str, status: int, elapsed: float) -> None:
    """Lightweight counters for the admin dashboard (Prometheus remains the source of truth)."""
    if not path.startswith("/api/"):
        return
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.incr("stats:api:requests")
        if status >= 500:
            pipe.incr("stats:api:failures")
        if status >= 400:
            pipe.incr("stats:api:client_errors" if status < 500 else "stats:api:server_errors")
        pipe.incrbyfloat("stats:api:latency_sum_ms", round(elapsed * 1000, 2))
        pipe.execute()
    except Exception:  # pragma: no cover
        pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response
