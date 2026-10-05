"""SkillDevelopmentConnector — Skill Development Department system (DEMO).

A *destination* system: the platform forwards verified applications here and
pushes the officer's decision. API key in `X-Dept-Key`.
"""
from __future__ import annotations

from app.integration.errors import InvalidSourceResponseError
from app.integration.sdk import BaseConnector

_STATUS_MAP = {"Received": "RECEIVED", "Sanctioned": "APPROVED", "NotSanctioned": "REJECTED"}


class SkillDevelopmentConnector(BaseConnector):
    key = "skill"
    name = "Skill Development Department Connector"
    system_name = "Skill Development Department"
    description = "Training enrolment system; receives applications and decisions."
    department_code = "SKILL_DEV"
    data_categories = []
    auth_type = "API_KEY"
    data_format = "JSON (PascalCase status codes)"
    capabilities = ["health_check", "submit_application", "get_application", "update_application"]
    default_base_url = "http://mock-skill:8000"
    base_url_env = "SKILL_BASE_URL"
    credential_env = {"api_key": "SKILL_API_KEY"}

    def authenticate(self) -> dict[str, str]:
        return {"X-Dept-Key": self.config.credentials.get("api_key", "")}

    def submit_application(self, payload: dict) -> dict:
        body = {
            "applicantRef": payload["citizen_id"],
            "applicantName": payload["full_name"],
            "schemeCode": payload["service_code"],
            "platformReference": payload["application_number"],
            "preferredTrade": payload["form"].get("preferred_trade", "GENERAL"),
            "preferredDistrict": payload["form"].get("preferred_district", "Unknown"),
            "trainingMode": payload["form"].get("training_mode", "CLASSROOM"),
            "eligibilityVerified": bool(payload.get("eligible")),
        }
        raw = self.post_json("/skill/applications", body)
        return self.transform_response(raw, "application")

    def get_application(self, reference: str) -> dict:
        return self.transform_response(self.get_json(f"/skill/applications/{reference}"), "application")

    def update_application(self, reference: str, payload: dict) -> dict:
        raw = self.post_json(
            f"/skill/applications/{reference}/decision",
            {"decision": payload["decision"], "remarks": payload.get("remarks"), "decidedBy": payload.get("decided_by")},
        )
        return self.transform_response(raw, "application")

    def transform_response(self, raw, kind="application", **context) -> dict:
        if not isinstance(raw, dict) or "enrolmentId" not in raw:
            raise InvalidSourceResponseError("Skill department response missing enrolmentId")
        return {
            "reference": raw["enrolmentId"],
            "status": _STATUS_MAP.get(raw.get("status"), str(raw.get("status", "UNKNOWN")).upper()),
            "batch_code": raw.get("batchCode"),
            "remarks": raw.get("remarks"),
            "updated_at": raw.get("updatedAt"),
        }
