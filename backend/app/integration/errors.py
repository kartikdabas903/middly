"""Connector error taxonomy. Connectors translate source failures into these."""
from __future__ import annotations


class ConnectorError(Exception):
    retryable = False
    reason = "ERROR"

    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


class SourceUnavailableError(ConnectorError):
    """Department system unreachable / 5xx / overloaded. Retryable."""

    retryable = True
    reason = "UNAVAILABLE"


class SourceTimeoutError(SourceUnavailableError):
    reason = "TIMEOUT"


class CircuitOpenError(SourceUnavailableError):
    """Fast-fail: the circuit breaker is open for this connector."""

    retryable = False
    reason = "CIRCUIT_OPEN"

    def __init__(self, message: str, *, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RecordNotFoundError(ConnectorError):
    reason = "NOT_FOUND"


class SourceAuthError(ConnectorError):
    reason = "AUTH_FAILED"


class InvalidSourceResponseError(ConnectorError):
    reason = "INVALID_RESPONSE"


class OperationNotSupportedError(ConnectorError):
    reason = "NOT_SUPPORTED"
