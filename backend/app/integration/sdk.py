"""Middly Connector SDK.

Every department integration implements `BaseConnector`. The core platform only
talks to this interface; it never knows a department's URLs, field names,
authentication scheme or data format. To onboard a new department, drop a
`connector.py` into /connectors/<department>/ — no core change is needed.

Contract:
    authenticate()        -> auth headers for the source system
    health_check()        -> HealthResult
    get_citizen(id)       -> SourceRecord in canonical vocabulary
    get_application(ref)  -> dict (department-side application status)
    submit_application()  -> dict (optional capability)
    transform_response()  -> map raw source payload to canonical fields
    handle_error(exc)     -> translate transport/HTTP failures to ConnectorError
"""
from __future__ import annotations

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar

import httpx

from app.integration.circuit_breaker import CircuitBreaker
from app.integration.errors import (
    CircuitOpenError,
    ConnectorError,
    InvalidSourceResponseError,
    OperationNotSupportedError,
    RecordNotFoundError,
    SourceAuthError,
    SourceTimeoutError,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

HEALTHY, DEGRADED, DOWN = "HEALTHY", "DEGRADED", "DOWN"


@dataclass
class ConnectorConfig:
    key: str
    base_url: str
    timeout_seconds: float = 3.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.25
    circuit_failure_threshold: int = 3
    circuit_open_seconds: int = 30
    credentials: dict[str, str] = field(default_factory=dict)
    correlation_id: str | None = None


@dataclass
class HealthResult:
    status: str
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceRecord:
    """A department's answer, already mapped to canonical field names."""

    connector_key: str
    category: str
    citizen_id: str
    canonical: dict[str, Any]
    source_updated_at: datetime | None = None
    source_reference: str | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CallStats:
    attempts: int = 0
    http_status: int | None = None
    latency_ms: float = 0.0


class BaseConnector(ABC):
    # ---- Plugin metadata (override in subclasses)
    key: ClassVar[str] = ""
    name: ClassVar[str] = ""
    system_name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    department_code: ClassVar[str | None] = None
    data_categories: ClassVar[list[str]] = []
    auth_type: ClassVar[str] = "NONE"
    data_format: ClassVar[str] = "JSON"
    capabilities: ClassVar[list[str]] = ["health_check"]
    version: ClassVar[str] = "1.0"
    default_base_url: ClassVar[str] = ""
    # Environment variable holding the base URL, and credential name -> env var.
    base_url_env: ClassVar[str | None] = None
    credential_env: ClassVar[dict[str, str]] = {}

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.breaker = CircuitBreaker(config.key, config.circuit_failure_threshold, config.circuit_open_seconds)
        self.last_call = CallStats()

    # ------------------------------------------------------------------ helpers
    @classmethod
    def resolve_base_url(cls) -> str:
        if cls.base_url_env and os.environ.get(cls.base_url_env):
            return os.environ[cls.base_url_env]
        return cls.default_base_url

    @classmethod
    def resolve_credentials(cls) -> dict[str, str]:
        return {name: os.environ.get(env, "") for name, env in cls.credential_env.items()}

    def _url(self, path: str) -> str:
        return self.config.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(self.config.timeout_seconds, connect=min(2.0, self.config.timeout_seconds)))

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        use_breaker: bool = True,
        retries: int | None = None,
        **kwargs,
    ) -> httpx.Response:
        """HTTP call with timeout, retry + exponential backoff (with jitter) and circuit breaking."""
        self.last_call = CallStats()
        if use_breaker and not self.breaker.allow():
            raise CircuitOpenError(
                f"{self.system_name} circuit is open; failing fast",
                retry_after_seconds=self.breaker.retry_after(),
            )
        max_attempts = 1 + (self.config.max_retries if retries is None else retries)
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.config.correlation_id:
            headers["X-Correlation-ID"] = self.config.correlation_id
        start = time.perf_counter()
        last_exc: ConnectorError | None = None
        with self._client() as client:
            for attempt in range(1, max_attempts + 1):
                self.last_call.attempts = attempt
                try:
                    if authenticated:
                        headers.update(self.authenticate())
                    resp = client.request(method, self._url(path), headers=headers, **kwargs)
                    self.last_call.http_status = resp.status_code
                    if resp.status_code == 401 and authenticated and attempt < max_attempts:
                        self.invalidate_auth()
                        raise SourceAuthError("Authentication rejected by source", http_status=401)
                    if resp.status_code >= 400:
                        raise self.handle_error(resp)
                    if use_breaker:
                        self.breaker.record_success()
                    self.last_call.latency_ms = (time.perf_counter() - start) * 1000
                    return resp
                except ConnectorError as exc:
                    last_exc = exc
                except Exception as exc:  # transport level
                    last_exc = self.handle_error(exc)
                if not (last_exc.retryable or isinstance(last_exc, SourceAuthError)) or attempt == max_attempts:
                    break
                delay = self.config.backoff_base_seconds * (2 ** (attempt - 1)) * (1 + random.random() * 0.2)
                logger.info("Retrying %s %s (attempt %s/%s) in %.2fs: %s", self.key, path, attempt + 1, max_attempts, delay, last_exc)
                time.sleep(delay)
        self.last_call.latency_ms = (time.perf_counter() - start) * 1000
        assert last_exc is not None
        if use_breaker and last_exc.retryable:
            self.breaker.record_failure()
        raise last_exc

    def get_json(self, path: str, **kwargs) -> Any:
        resp = self.request("GET", path, **kwargs)
        return self._parse_json(resp)

    def post_json(self, path: str, payload: dict, **kwargs) -> Any:
        resp = self.request("POST", path, json=payload, **kwargs)
        return self._parse_json(resp)

    @staticmethod
    def _parse_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except ValueError as exc:
            raise InvalidSourceResponseError("Source returned a non-JSON body", http_status=resp.status_code) from exc

    # ------------------------------------------------------------------ contract
    @abstractmethod
    def authenticate(self) -> dict[str, str]:
        """Return the headers required by the source system."""

    def invalidate_auth(self) -> None:
        """Drop cached credentials (called after a 401)."""

    def health_check(self) -> HealthResult:
        start = time.perf_counter()
        try:
            resp = self.request("GET", "/health", authenticated=False, use_breaker=False, retries=0)
            latency = (time.perf_counter() - start) * 1000
            body = self._parse_json(resp)
            status = str(body.get("status", "UP")).upper()
            if status in {"UP", "OK", "HEALTHY"}:
                status = DEGRADED if latency > 1500 else HEALTHY
            elif status == "DEGRADED":
                status = DEGRADED
            else:
                status = DOWN
            return HealthResult(status=status, latency_ms=round(latency, 1), message=body.get("message"), details=body)
        except ConnectorError as exc:
            return HealthResult(status=DOWN, latency_ms=round((time.perf_counter() - start) * 1000, 1), message=exc.message)

    def get_citizen(self, citizen_id: str) -> SourceRecord:
        raise OperationNotSupportedError(f"{self.key} does not provide citizen records")

    def get_application(self, reference: str) -> dict[str, Any]:
        raise OperationNotSupportedError(f"{self.key} does not expose applications")

    def submit_application(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise OperationNotSupportedError(f"{self.key} does not accept applications")

    def update_application(self, reference: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise OperationNotSupportedError(f"{self.key} does not accept application updates")

    def transform_response(self, raw: Any, kind: str = "citizen", **context) -> Any:
        """Map a raw source payload into the canonical vocabulary."""
        return raw

    def handle_error(self, error: Exception | httpx.Response) -> ConnectorError:
        if isinstance(error, httpx.Response):
            code = error.status_code
            if code == 404:
                return RecordNotFoundError(f"{self.system_name}: record not found", http_status=code)
            if code in (401, 403):
                return SourceAuthError(f"{self.system_name}: authentication failed", http_status=code)
            if code == 429 or code >= 500:
                return SourceUnavailableError(f"{self.system_name} unavailable (HTTP {code})", http_status=code)
            return InvalidSourceResponseError(f"{self.system_name}: unexpected HTTP {code}", http_status=code)
        if isinstance(error, httpx.TimeoutException):
            return SourceTimeoutError(f"{self.system_name} timed out after {self.config.timeout_seconds}s")
        if isinstance(error, httpx.TransportError):
            return SourceUnavailableError(f"{self.system_name} unreachable: {error.__class__.__name__}")
        if isinstance(error, ConnectorError):
            return error
        return ConnectorError(f"{self.system_name}: {error}")
