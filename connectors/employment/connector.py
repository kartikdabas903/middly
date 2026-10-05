"""EmploymentConnector — Employment Registry (DEMO).

Source quirks handled here: `{status, data}` envelope, `candidateName`, legacy
status codes (UNEMP / EMP / SALARIED), HTTP Basic auth.
"""
from __future__ import annotations

from app.integration.auth import basic_auth_header
from app.integration.errors import InvalidSourceResponseError
from app.integration.normalize import clean_text, normalize_employment_status, normalize_name, parse_date, parse_datetime
from app.integration.sdk import BaseConnector, SourceRecord


class EmploymentConnector(BaseConnector):
    key = "employment"
    name = "Employment Registry Connector"
    system_name = "Employment Registry"
    description = "Job-seeker registration and current employment status."
    department_code = "EMPLOYMENT_DEPT"
    data_categories = ["EMPLOYMENT"]
    auth_type = "HTTP_BASIC"
    data_format = "JSON ({status,data} envelope, legacy codes)"
    capabilities = ["health_check", "get_citizen"]
    default_base_url = "http://mock-employment:8000"
    base_url_env = "EMPLOYMENT_BASE_URL"
    credential_env = {"username": "EMPLOYMENT_BASIC_USER", "password": "EMPLOYMENT_BASIC_PASSWORD"}

    def authenticate(self) -> dict[str, str]:
        return basic_auth_header(self.config.credentials.get("username", ""), self.config.credentials.get("password", ""))

    def get_citizen(self, citizen_id: str) -> SourceRecord:
        raw = self.get_json(f"/employment/citizens/{citizen_id}")
        return self.transform_response(raw, "citizen", citizen_id=citizen_id)

    def transform_response(self, raw, kind="citizen", **context) -> SourceRecord:
        if not isinstance(raw, dict) or raw.get("status") != "OK" or not isinstance(raw.get("data"), dict):
            raise InvalidSourceResponseError("Employment payload envelope invalid")
        data = raw["data"]
        warnings: list[dict] = []
        status = normalize_employment_status(data.get("employmentStatus"))
        if status is None:
            warnings.append({"field": "employment_status", "issue": "INVALID_FORMAT", "message": f"Unknown status code {data.get('employmentStatus')!r}"})
        dob = None
        try:
            dob = parse_date(data.get("dateOfBirth"), ("%Y-%m-%d",))
        except ValueError:
            warnings.append({"field": "date_of_birth", "issue": "INVALID_FORMAT", "message": "Unparseable date of birth"})
        canonical = {
            "citizen_id": str(data.get("citizenRef") or context.get("citizen_id")),
            "full_name": normalize_name(data.get("candidateName")),
            "date_of_birth": dob.isoformat() if dob else None,
            "employment_status": status,
            "employment": {
                "registration_id": clean_text(data.get("registrationId")),
                "registered_on": data.get("registeredOn"),
                "skills": [s for s in (data.get("skills") or []) if isinstance(s, str)],
                "last_employer": clean_text(data.get("lastEmployer")),
            },
        }
        return SourceRecord(
            connector_key=self.key,
            category="EMPLOYMENT",
            citizen_id=canonical["citizen_id"],
            canonical=canonical,
            source_updated_at=parse_datetime(data.get("lastVerified")),
            source_reference=data.get("registrationId"),
            warnings=warnings,
        )
