"""EducationConnector — Education Registry (DEMO).

Source quirks handled here: envelope `{registry, record}`, `student_name`,
YYYY/MM/DD dates, list of qualifications (we derive the highest), API-key auth.
"""
from __future__ import annotations

from app.integration.errors import InvalidSourceResponseError
from app.integration.normalize import clean_text, level_rank, normalize_name, parse_date, parse_datetime, qualification_level
from app.integration.sdk import BaseConnector, SourceRecord


class EducationConnector(BaseConnector):
    key = "education"
    name = "Education Registry Connector"
    system_name = "Education Registry"
    description = "Academic qualifications and passing years."
    department_code = "EDUCATION_DEPT"
    data_categories = ["EDUCATION"]
    auth_type = "API_KEY"
    data_format = "JSON (snake_case envelope, YYYY/MM/DD)"
    capabilities = ["health_check", "get_citizen"]
    default_base_url = "http://mock-education:8000"
    base_url_env = "EDUCATION_BASE_URL"
    credential_env = {"api_key": "EDUCATION_API_KEY"}

    def authenticate(self) -> dict[str, str]:
        return {"X-API-Key": self.config.credentials.get("api_key", "")}

    def get_citizen(self, citizen_id: str) -> SourceRecord:
        raw = self.get_json(f"/education/citizens/{citizen_id}")
        return self.transform_response(raw, "citizen", citizen_id=citizen_id)

    def transform_response(self, raw, kind="citizen", **context) -> SourceRecord:
        record = raw.get("record") if isinstance(raw, dict) else None
        if not isinstance(record, dict) or not isinstance(record.get("qualifications"), list):
            raise InvalidSourceResponseError("Education payload missing `record.qualifications`")
        warnings: list[dict] = []
        quals = []
        for q in record["qualifications"]:
            level = qualification_level(q.get("level"))
            if level is None:
                warnings.append({"field": "education", "issue": "INVALID_FORMAT", "message": f"Unknown qualification {q.get('level')!r}"})
                continue
            quals.append({**q, "_level": level})
        highest = max(quals, key=lambda q: (level_rank(q["_level"]), q.get("passing_year") or 0), default=None)
        dob = None
        try:
            dob = parse_date(record.get("date_of_birth"), ("%Y/%m/%d",))
        except ValueError:
            warnings.append({"field": "date_of_birth", "issue": "INVALID_FORMAT", "message": "Unparseable date of birth"})
        education = None
        if highest:
            education = {
                "highest_qualification": clean_text(highest.get("level")),
                "qualification_level": highest["_level"],
                "passing_year": highest.get("passing_year"),
                "institution": clean_text(highest.get("institution") or highest.get("board")),
                "stream": clean_text(highest.get("stream")),
                "qualifications_count": len(quals),
            }
        canonical = {
            "citizen_id": str(record.get("citizen_ref") or context.get("citizen_id")),
            "full_name": normalize_name(record.get("student_name")),
            "date_of_birth": dob.isoformat() if dob else None,
            "education": education,
        }
        return SourceRecord(
            connector_key=self.key,
            category="EDUCATION",
            citizen_id=canonical["citizen_id"],
            canonical=canonical,
            source_updated_at=parse_datetime(record.get("record_updated_on")),
            source_reference=record.get("enrollment_no"),
            warnings=warnings,
        )
