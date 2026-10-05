"""Domain errors mapped to a uniform JSON error envelope."""
from __future__ import annotations

from typing import Any


class PlatformError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, details: Any | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(PlatformError):
    status_code = 404
    code = "NOT_FOUND"


class AuthenticationError(PlatformError):
    status_code = 401
    code = "UNAUTHENTICATED"


class ForbiddenError(PlatformError):
    status_code = 403
    code = "FORBIDDEN"


class ConsentRequiredError(PlatformError):
    status_code = 403
    code = "CONSENT_REQUIRED"


class ConflictError(PlatformError):
    status_code = 409
    code = "CONFLICT"


class DomainValidationError(PlatformError):
    status_code = 422
    code = "VALIDATION_FAILED"


class InvalidStateError(PlatformError):
    status_code = 409
    code = "INVALID_STATE"


class SourceUnavailableError(PlatformError):
    status_code = 503
    code = "SOURCE_UNAVAILABLE"


class RateLimitedError(PlatformError):
    status_code = 429
    code = "RATE_LIMITED"
