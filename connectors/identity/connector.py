"""IdentityConnector — Identity Service (DEMO).

Source quirks handled here: camelCase fields, DD-MM-YYYY dates, gender codes,
state codes, free-form phone numbers, OAuth2 client-credentials auth.
The fake `aadhaarRef` is deliberately dropped — the platform never stores it.
"""
from __future__ import annotations

from app.integration.auth import ClientCredentialsTokenProvider
from app.integration.errors import InvalidSourceResponseError
from app.integration.normalize import (
    clean_text,
    is_valid_mobile,
    mask_mobile,
    normalize_gender,
    normalize_mobile,
    normalize_name,
    normalize_state,
    parse_date,
    parse_datetime,
)
from app.integration.sdk import BaseConnector, SourceRecord


class IdentityConnector(BaseConnector):
    key = "identity"
    name = "Identity Service Connector"
    system_name = "Identity Service"
    description = "Resident identity attributes: name, date of birth, gender, contact and address."
    department_code = "IDENTITY_AUTHORITY"
    data_categories = ["IDENTITY"]
    auth_type = "OAUTH2_CLIENT_CREDENTIALS"
    data_format = "JSON (camelCase, DD-MM-YYYY)"
    capabilities = ["health_check", "get_citizen"]
    default_base_url = "http://mock-identity:8000"
    base_url_env = "IDENTITY_BASE_URL"
    credential_env = {"client_id": "IDENTITY_CLIENT_ID", "client_secret": "IDENTITY_CLIENT_SECRET"}

    def __init__(self, config):
        super().__init__(config)
        self._tokens = ClientCredentialsTokenProvider(
            cache_key=self.key,
            token_url=self._url("/identity/oauth/token"),
            client_id=config.credentials.get("client_id", ""),
            client_secret=config.credentials.get("client_secret", ""),
            timeout=config.timeout_seconds,
        )

    def authenticate(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.token()}"}

    def invalidate_auth(self) -> None:
        self._tokens.invalidate()

    def get_citizen(self, citizen_id: str) -> SourceRecord:
        raw = self.get_json(f"/identity/citizens/{citizen_id}")
        return self.transform_response(raw, "citizen", citizen_id=citizen_id)

    def transform_response(self, raw, kind="citizen", **context) -> SourceRecord:
        if not isinstance(raw, dict) or "fullName" not in raw:
            raise InvalidSourceResponseError("Identity payload missing mandatory attributes")
        warnings: list[dict] = []
        address = raw.get("address") or {}
        mobile_digits = normalize_mobile(raw.get("mobileNumber"))
        if mobile_digits and not is_valid_mobile(mobile_digits):
            warnings.append({"field": "mobile", "issue": "INVALID_FORMAT", "message": "Mobile number is not a valid 10-digit number"})
            mobile_digits = None
        dob = None
        try:
            dob = parse_date(raw.get("dob"), ("%d-%m-%Y",))
        except ValueError:
            warnings.append({"field": "date_of_birth", "issue": "INVALID_FORMAT", "message": f"Unparseable date {raw.get('dob')!r}"})
        canonical = {
            "citizen_id": str(raw.get("citizenId") or context.get("citizen_id")),
            "full_name": normalize_name(raw.get("fullName")),
            "date_of_birth": dob.isoformat() if dob else None,
            "gender": normalize_gender(raw.get("gender")),
            "mobile": mask_mobile(mobile_digits),
            "email": clean_text(raw.get("emailId")),
            "address": clean_text(address.get("line1")),
            "district": clean_text(address.get("district")),
            "state": normalize_state(address.get("stateCode")),
            "pincode": clean_text(address.get("pincode")),
        }
        return SourceRecord(
            connector_key=self.key,
            category="IDENTITY",
            citizen_id=canonical["citizen_id"],
            canonical=canonical,
            source_updated_at=parse_datetime(raw.get("lastUpdated")),
            warnings=warnings,
        )
