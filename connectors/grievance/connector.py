"""GrievanceConnector — Public Grievance Redressal system (DEMO).

The platform registers grievances here and *reads* their status for unified
tracking. OAuth2 client credentials.
"""
from __future__ import annotations

from app.integration.auth import ClientCredentialsTokenProvider
from app.integration.errors import InvalidSourceResponseError
from app.integration.sdk import BaseConnector


class GrievanceConnector(BaseConnector):
    key = "grievance"
    name = "Grievance Redressal Connector"
    system_name = "Public Grievance System"
    description = "Registers citizen grievances and synchronises their status."
    department_code = "GRIEVANCE_CELL"
    data_categories = []
    auth_type = "OAUTH2_CLIENT_CREDENTIALS"
    data_format = "JSON (ticket model)"
    capabilities = ["health_check", "submit_application", "get_application"]
    default_base_url = "http://mock-grievance:8000"
    base_url_env = "GRIEVANCE_BASE_URL"
    credential_env = {"client_id": "GRIEVANCE_CLIENT_ID", "client_secret": "GRIEVANCE_CLIENT_SECRET"}

    def __init__(self, config):
        super().__init__(config)
        self._tokens = ClientCredentialsTokenProvider(
            cache_key=self.key,
            token_url=self._url("/grievances/oauth/token"),
            client_id=config.credentials.get("client_id", ""),
            client_secret=config.credentials.get("client_secret", ""),
            timeout=config.timeout_seconds,
        )

    def authenticate(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.token()}"}

    def invalidate_auth(self) -> None:
        self._tokens.invalidate()

    def submit_application(self, payload: dict) -> dict:
        form = payload["form"]
        raw = self.post_json(
            "/grievances",
            {
                "citizen_ref": payload["citizen_id"],
                "category": form.get("category", "GENERAL"),
                "subject": form.get("subject", ""),
                "description": form.get("description", ""),
                "platform_reference": payload["application_number"],
            },
        )
        return self.transform_response(raw, "application")

    def get_application(self, reference: str) -> dict:
        return self.transform_response(self.get_json(f"/grievances/{reference}"), "application")

    def transform_response(self, raw, kind="application", **context) -> dict:
        if not isinstance(raw, dict) or "ticketNo" not in raw:
            raise InvalidSourceResponseError("Grievance response missing ticketNo")
        history = raw.get("history") or []
        return {
            "reference": raw["ticketNo"],
            "status": str(raw.get("state", "UNKNOWN")).upper(),
            "assigned_to": raw.get("assignedTo"),
            "remarks": history[-1].get("remarks") if history else None,
            "history": history,
        }
