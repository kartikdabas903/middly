from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.context import get_context
from app.core.errors import PlatformError
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.integration.registry import registry

logger = logging.getLogger(__name__)

DESCRIPTION = """
**Middly — interoperability platform for public services.**

> Sandbox deployments connect to sample department systems with fictitious data.

Secure middleware connecting independent department systems through reusable connectors,
consent-based data sharing, master data management, configurable workflows and events.

Authenticate with a Keycloak access token (`Authorization: Bearer <token>`). Every response carries `X-Request-ID`.
"""


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details, "correlation_id": get_context().correlation_id}},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.discover()
    try:
        from app.db.session import get_sessionmaker
        from app.services.connector_service import sync_registry

        with get_sessionmaker()() as db:
            sync_registry(db)
            db.commit()
    except Exception as exc:  # DB not migrated yet (e.g. first boot) — seeding will sync later
        logger.warning("Connector registry sync skipped: %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Middly Interoperability Platform API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(PlatformError)
    async def platform_error(_: Request, exc: PlatformError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        resp = _error(exc.status_code, exc.code, exc.message, exc.details)
        if headers:
            resp.headers.update(headers)
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return _error(422, "VALIDATION_FAILED", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", "An unexpected error occurred. Quote the correlation id when reporting.")

    app.include_router(health_router)
    app.include_router(api_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        from app.services.metrics_collector import refresh_business_gauges

        refresh_business_gauges()
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs", "sandbox": settings.demo_mode}

    return app


app = create_app()
