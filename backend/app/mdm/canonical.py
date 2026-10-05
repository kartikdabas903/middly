"""Canonical citizen data model.

Connectors map their source fields onto these names; the core then validates
every fragment against this schema — connector output is never trusted blindly.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator

Gender = Literal["MALE", "FEMALE", "OTHER"]
EmploymentStatus = Literal["UNEMPLOYED", "EMPLOYED", "SELF_EMPLOYED", "STUDENT"]


class EducationInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    highest_qualification: str = Field(..., min_length=1, max_length=80)
    qualification_level: str
    passing_year: int | None = Field(default=None, ge=1950, le=2035)
    institution: str | None = None
    stream: str | None = None
    qualifications_count: int | None = None


class EmploymentInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    registration_id: str | None = None
    registered_on: str | None = None
    skills: list[str] = Field(default_factory=list)
    last_employer: str | None = None


class CanonicalFragment(BaseModel):
    """Partial canonical record contributed by one source system."""

    model_config = ConfigDict(extra="ignore")

    citizen_id: str = Field(..., pattern=r"^\d{6,12}$")
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    date_of_birth: date | None = None
    gender: Gender | None = None
    mobile: str | None = Field(default=None, pattern=r"^X*\d{4}$")
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    education: EducationInfo | None = None
    employment_status: EmploymentStatus | None = None
    employment: EmploymentInfo | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_dob(cls, value: date | None) -> date | None:
        if value is None:
            return value
        if value > date.today() or value.year < 1900:
            raise ValueError("date_of_birth outside plausible range")
        return value


CANONICAL_FIELDS = [
    "citizen_id", "full_name", "date_of_birth", "gender", "mobile", "email", "address",
    "district", "state", "pincode", "education", "employment_status",
]


def validate_fragment(data: dict[str, Any]) -> tuple[CanonicalFragment, list[dict[str, Any]]]:
    """Validate a connector fragment; invalid fields are dropped and reported (never trusted)."""
    issues: list[dict[str, Any]] = []
    candidate = dict(data)
    for _ in range(len(candidate) + 1):
        try:
            return CanonicalFragment.model_validate(candidate), issues
        except ValidationError as exc:
            bad_fields = {str(err["loc"][0]) for err in exc.errors() if err.get("loc")}
            if "citizen_id" in bad_fields or not bad_fields:
                raise
            for err in exc.errors():
                field = str(err["loc"][0])
                if field in candidate:
                    issues.append({"field": field, "issue": "INVALID_FORMAT", "message": f"{field}: {err['msg']}", "value": _safe_preview(candidate.get(field))})
            for f in bad_fields:
                candidate.pop(f, None)
    raise ValueError("Unable to validate fragment")


def _safe_preview(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 40 else text[:37] + "..."
