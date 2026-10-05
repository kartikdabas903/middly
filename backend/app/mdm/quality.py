"""Data-quality rules applied to aggregated citizen data.

Pure functions (no DB access) so they are easy to unit test. Duplicate detection
receives candidate records from the caller.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.integration.normalize import name_key, name_similarity, names_compatible
from app.mdm.merge import SourceFragment
from app.models.enums import DQIssueType, DQSeverity, SourceQualityStatus

REQUIRED_FIELDS: dict[str, list[str]] = {
    "IDENTITY": ["full_name", "date_of_birth", "gender", "state", "district"],
    "EDUCATION": ["education"],
    "EMPLOYMENT": ["employment_status"],
}


@dataclass
class QualityIssue:
    source_system: str
    issue_type: str
    severity: str
    message: str
    field: str | None = None
    details: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityReport:
    issues: list[QualityIssue] = dc_field(default_factory=list)
    source_status: dict[str, dict[str, Any]] = dc_field(default_factory=dict)

    @property
    def overall(self) -> str:
        statuses = {s["status"] for s in self.source_status.values()}
        for level in (SourceQualityStatus.UNAVAILABLE, SourceQualityStatus.CONFLICT, SourceQualityStatus.NOT_FOUND, SourceQualityStatus.WARNING):
            if level in statuses:
                return level.value
        return SourceQualityStatus.VERIFIED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "sources": self.source_status,
            "issues": [i.to_dict() for i in self.issues],
            "counts": {
                "critical": sum(1 for i in self.issues if i.severity == DQSeverity.CRITICAL),
                "warning": sum(1 for i in self.issues if i.severity == DQSeverity.WARNING),
                "info": sum(1 for i in self.issues if i.severity == DQSeverity.INFO),
            },
        }


def _status_rank(status: str) -> int:
    order = [SourceQualityStatus.VERIFIED, SourceQualityStatus.WARNING, SourceQualityStatus.NOT_FOUND, SourceQualityStatus.CONFLICT, SourceQualityStatus.UNAVAILABLE]
    return [s.value for s in order].index(status) if status in [s.value for s in order] else 0


def evaluate_quality(
    fragments: list[SourceFragment],
    *,
    unavailable: dict[str, str] | None = None,
    not_found: dict[str, str] | None = None,
    connector_warnings: dict[str, list[dict[str, Any]]] | None = None,
    duplicate_candidates: list[dict[str, Any]] | None = None,
    stale_after_days: int = 365,
    now: datetime | None = None,
) -> QualityReport:
    """Run all checks. `unavailable` / `not_found` map system name -> reason."""
    now = now or datetime.now(timezone.utc)
    report = QualityReport()

    def mark(system: str, category: str, status: SourceQualityStatus, reason: str | None = None):
        current = report.source_status.get(system)
        if current is None or _status_rank(status.value) > _status_rank(current["status"]):
            report.source_status[system] = {"status": status.value, "category": category, "reason": reason}
        elif reason and not current.get("reason"):
            current["reason"] = reason

    for system, reason in (unavailable or {}).items():
        report.issues.append(QualityIssue(system, DQIssueType.SOURCE_UNAVAILABLE, DQSeverity.CRITICAL, f"{system} temporarily unavailable: {reason}"))
        mark(system, "", SourceQualityStatus.UNAVAILABLE, "Temporarily unavailable")
    for system, reason in (not_found or {}).items():
        report.issues.append(QualityIssue(system, DQIssueType.RECORD_NOT_FOUND, DQSeverity.WARNING, f"No record found in {system}"))
        mark(system, "", SourceQualityStatus.NOT_FOUND, reason)

    for frag in fragments:
        mark(frag.system_name, frag.category, SourceQualityStatus.VERIFIED)
        # 1. Missing required fields
        for req in REQUIRED_FIELDS.get(frag.category, []):
            if getattr(frag.fragment, req, None) in (None, "", []):
                report.issues.append(QualityIssue(frag.system_name, DQIssueType.MISSING_FIELD, DQSeverity.WARNING, f"Required field '{req}' missing", field=req))
                mark(frag.system_name, frag.category, SourceQualityStatus.WARNING, f"Missing {req}")
        # 2. Format issues reported during transformation/validation
        for w in (connector_warnings or {}).get(frag.system_name, []):
            report.issues.append(QualityIssue(frag.system_name, DQIssueType.INVALID_FORMAT, DQSeverity.WARNING, w.get("message", "Invalid format"), field=w.get("field"), details={k: v for k, v in w.items() if k not in {"message", "field"}}))
            mark(frag.system_name, frag.category, SourceQualityStatus.WARNING, "Invalid field format")
        # 3. Stale data
        if frag.source_updated_at:
            try:
                updated = datetime.fromisoformat(frag.source_updated_at)
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if now - updated > timedelta(days=stale_after_days):
                    age = (now - updated).days
                    report.issues.append(QualityIssue(frag.system_name, DQIssueType.STALE_DATA, DQSeverity.INFO, f"Record last updated {age} days ago", details={"last_updated": frag.source_updated_at}))
                    mark(frag.system_name, frag.category, SourceQualityStatus.WARNING, f"Stale record ({age} days old)")
            except ValueError:
                pass

    # 4. Cross-source consistency (identity is the reference)
    reference = next((f for f in fragments if f.category == "IDENTITY"), None)
    if reference:
        ref_name, ref_dob = reference.fragment.full_name, reference.fragment.date_of_birth
        for frag in fragments:
            if frag is reference:
                continue
            other_name = frag.fragment.full_name
            if ref_name and other_name and name_key(ref_name) != name_key(other_name):
                if names_compatible(ref_name, other_name):
                    report.issues.append(QualityIssue(frag.system_name, DQIssueType.NAME_VARIATION, DQSeverity.INFO, f"Name variation: '{other_name}' vs identity '{ref_name}' (middle name)", field="full_name", details={"identity": ref_name, "source": other_name}))
                    mark(frag.system_name, frag.category, SourceQualityStatus.WARNING, "Minor name variation")
                else:
                    score = round(name_similarity(ref_name, other_name), 2)
                    report.issues.append(QualityIssue(frag.system_name, DQIssueType.NAME_CONFLICT, DQSeverity.WARNING, f"Name mismatch between systems: '{other_name}' vs identity '{ref_name}'", field="full_name", details={"identity": ref_name, "source": other_name, "similarity": score}))
                    mark(frag.system_name, frag.category, SourceQualityStatus.CONFLICT, "Name mismatch between systems")
                    mark(reference.system_name, reference.category, SourceQualityStatus.CONFLICT, "Name mismatch between systems")
            other_dob = frag.fragment.date_of_birth
            if ref_dob and other_dob and ref_dob != other_dob:
                report.issues.append(QualityIssue(frag.system_name, DQIssueType.DOB_CONFLICT, DQSeverity.CRITICAL, f"Date of birth mismatch: {other_dob.isoformat()} vs identity {ref_dob.isoformat()}", field="date_of_birth", details={"identity": ref_dob.isoformat(), "source": other_dob.isoformat()}))
                mark(frag.system_name, frag.category, SourceQualityStatus.CONFLICT, "Date of birth mismatch")

        # 5. Duplicate citizen records in the golden-record store
        for dup in duplicate_candidates or []:
            report.issues.append(QualityIssue(reference.system_name, DQIssueType.DUPLICATE_RECORD, DQSeverity.WARNING, f"Possible duplicate citizen record {dup['citizen_id']} (same name and date of birth)", details={"duplicate_citizen_id": dup["citizen_id"], "district": dup.get("district")}))
            mark(reference.system_name, reference.category, SourceQualityStatus.WARNING, "Possible duplicate record")

    return report
