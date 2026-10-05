"""Validated request bodies (all inputs are size-bounded and strictly typed)."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DataCategory


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApplicationCreate(_Strict):
    service_code: str = Field(..., min_length=2, max_length=60, pattern=r"^[A-Z0-9_]+$", examples=["SKILL_DEV_SCHEME"])
    form_data: dict[str, Any] = Field(default_factory=dict, examples=[{"preferred_trade": "ELECTRICIAN", "preferred_district": "Pune", "training_mode": "CLASSROOM"}])

    @field_validator("form_data")
    @classmethod
    def _bounded(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > 20:
            raise ValueError("Too many form fields")
        for key, value in v.items():
            if len(key) > 60 or (isinstance(value, str) and len(value) > 2000):
                raise ValueError("Form field too long")
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ValueError("Form values must be scalars")
        return v


class GrievanceCreate(_Strict):
    category: Literal["SCHEME_BENEFIT", "RECORD_CORRECTION", "SERVICE_DELAY", "OTHER"]
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)


class ConsentCreate(_Strict):
    application_id: uuid.UUID
    data_categories: list[DataCategory] = Field(..., min_length=1, max_length=10)


class ConsentRevoke(_Strict):
    reason: str | None = Field(default=None, max_length=500)


class OfficerDecision(_Strict):
    remarks: str | None = Field(default=None, max_length=1000)


class ClarificationRequest(_Strict):
    question: str = Field(..., min_length=5, max_length=1000)


class ClarificationResponse(_Strict):
    response: str = Field(..., min_length=2, max_length=2000)


class WithdrawRequest(_Strict):
    reason: str | None = Field(default=None, max_length=500)


class ConnectorUpdate(_Strict):
    enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, ge=0.5, le=30)
    max_retries: int | None = Field(default=None, ge=0, le=5)


class FaultRequest(_Strict):
    mode: Literal["HEALTHY", "DEGRADED", "SLOW", "DOWN", "FLAKY"]


class ResolveIssue(_Strict):
    note: str | None = Field(default=None, max_length=500)
