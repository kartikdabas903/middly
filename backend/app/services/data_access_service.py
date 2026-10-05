"""Consent-checked data retrieval and master-data consolidation.

fetch_category():  consent check -> connector call -> canonical validation -> audit
consolidate():     merge fragments -> data-quality checks -> golden record + DQ issues
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.integration.errors import ConnectorError, RecordNotFoundError
from app.mdm.canonical import validate_fragment
from app.mdm.merge import MergedProfile, SourceFragment, merge_fragments
from app.mdm.quality import QualityReport, evaluate_quality
from app.models import Citizen, Connector, DataQualityIssue
from app.models.enums import DQIssueType, DQSeverity
from app.services import connector_service, consent_service
from app.services.audit_service import audit

logger = logging.getLogger(__name__)

PLATFORM = "Middly Platform"


@dataclass
class FetchResult:
    category: str
    connector_key: str
    system_name: str
    found: bool = True
    fragment: SourceFragment | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    canonical: dict[str, Any] | None = None
    source_updated_at: str | None = None
    source_reference: str | None = None

    def to_output(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "connector": self.connector_key,
            "system": self.system_name,
            "found": self.found,
            "canonical": self.canonical,
            "warnings": self.warnings,
            "source_updated_at": self.source_updated_at,
            "source_reference": self.source_reference,
            "fetched_at": clock.now().isoformat(),
        }


def ensure_citizen(db: Session, citizen_id: str) -> Citizen:
    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        citizen = Citizen(citizen_id=citizen_id, field_provenance={}, source_status={})
        db.add(citizen)
        db.flush()
    return citizen


def fetch_category(
    db: Session,
    *,
    citizen_id: str,
    category: str,
    connector_key: str,
    purpose: str | None,
    requester_department_id: uuid.UUID | None,
    requester_name: str,
    application_id: uuid.UUID | None = None,
    self_access: bool = False,
) -> FetchResult:
    row = connector_service.get_row(db, connector_key)
    if self_access:
        consent_service.log_self_access(db, citizen_id, category, connector_key)
    else:
        assert requester_department_id is not None
        consent_service.verify(
            db, citizen_id=citizen_id, department_id=requester_department_id, category=category,
            purpose=purpose, application_id=application_id, connector_key=connector_key,
        )
    action = f"SYSTEM_ACCESSED_{category}_DATA"
    try:
        record = connector_service.invoke(db, connector_key, "get_citizen", citizen_id, application_id=application_id, citizen_id=citizen_id)
    except RecordNotFoundError:
        audit(action, "citizen", citizen_id, status="NOT_FOUND", source_system=row.system_name, destination_system=requester_name)
        return FetchResult(category=category, connector_key=connector_key, system_name=row.system_name, found=False)
    except ConnectorError as exc:
        audit("SYSTEM_FETCH_FAILED", "citizen", citizen_id, status="FAILURE", source_system=row.system_name, destination_system=requester_name,
              details={"category": category, "reason": exc.reason, "error": exc.message, "application_id": str(application_id) if application_id else None})
        _open_issue(db, citizen_id, application_id, row.system_name, DQIssueType.SOURCE_UNAVAILABLE if exc.retryable or exc.reason == "CIRCUIT_OPEN" else DQIssueType.INVALID_RESPONSE,
                    DQSeverity.CRITICAL, f"{row.system_name}: {exc.message}")
        raise

    # Never trust connector output blindly: re-validate against the canonical schema.
    try:
        fragment, invalid = validate_fragment(record.canonical)
    except Exception as exc:
        audit("SYSTEM_FETCH_FAILED", "citizen", citizen_id, status="INVALID_RESPONSE", source_system=row.system_name, details={"error": str(exc)[:300]})
        _open_issue(db, citizen_id, application_id, row.system_name, DQIssueType.INVALID_RESPONSE, DQSeverity.CRITICAL, f"{row.system_name} returned an invalid payload")
        raise ConnectorError(f"{row.system_name} returned an invalid payload") from exc
    if fragment.citizen_id != citizen_id:
        _open_issue(db, citizen_id, application_id, row.system_name, DQIssueType.INVALID_RESPONSE, DQSeverity.CRITICAL, f"{row.system_name} returned a record for a different citizen")
        raise ConnectorError(f"{row.system_name} returned a record for a different citizen")

    _resolve_availability_issues(db, citizen_id, row.system_name)
    audit(action, "citizen", citizen_id, source_system=row.system_name, destination_system=requester_name,
          details={"category": category, "application_id": str(application_id) if application_id else None, "self_access": self_access})
    canonical = fragment.model_dump(mode="json", exclude_none=True)
    updated = record.source_updated_at.isoformat() if record.source_updated_at else None
    return FetchResult(
        category=category,
        connector_key=connector_key,
        system_name=row.system_name,
        found=True,
        fragment=SourceFragment(category, connector_key, row.system_name, fragment, updated, record.source_reference),
        warnings=list(record.warnings) + invalid,
        canonical=canonical,
        source_updated_at=updated,
        source_reference=record.source_reference,
    )


def fragment_from_output(output: dict[str, Any]) -> SourceFragment | None:
    if not output.get("found") or not output.get("canonical"):
        return None
    fragment, _ = validate_fragment(output["canonical"])
    return SourceFragment(output["category"], output["connector"], output["system"], fragment, output.get("source_updated_at"), output.get("source_reference"))


def consolidate(
    db: Session,
    citizen_id: str,
    outputs: list[dict[str, Any]],
    *,
    application_id: uuid.UUID | None = None,
    unavailable: dict[str, str] | None = None,
) -> tuple[MergedProfile, QualityReport]:
    fragments = [f for f in (fragment_from_output(o) for o in outputs) if f]
    not_found = {o["system"]: "No record for this citizen" for o in outputs if not o.get("found")}
    warnings = {o["system"]: o.get("warnings") or [] for o in outputs if o.get("found")}
    merged = merge_fragments(citizen_id, fragments)

    duplicates = []
    name, dob = merged.values.get("full_name"), merged.values.get("date_of_birth")
    if name and dob:
        stmt = select(Citizen).where(
            func.lower(Citizen.full_name) == name.lower(),
            Citizen.date_of_birth == date.fromisoformat(dob),
            Citizen.citizen_id != citizen_id,
        )
        duplicates = [{"citizen_id": c.citizen_id, "district": c.district} for c in db.scalars(stmt)]

    report = evaluate_quality(
        fragments, unavailable=unavailable, not_found=not_found, connector_warnings=warnings,
        duplicate_candidates=duplicates, stale_after_days=get_settings().stale_data_days, now=clock.now(),
    )
    _persist_golden_record(db, merged, report)
    _replace_issues(db, citizen_id, application_id, report)
    return merged, report


def _persist_golden_record(db: Session, merged: MergedProfile, report: QualityReport) -> Citizen:
    citizen = ensure_citizen(db, merged.citizen_id)
    v = merged.values
    citizen.full_name = v.get("full_name", citizen.full_name)
    citizen.date_of_birth = date.fromisoformat(v["date_of_birth"]) if v.get("date_of_birth") else citizen.date_of_birth
    for f in ("gender", "mobile", "email", "address", "district", "state", "pincode", "employment_status"):
        if v.get(f) is not None:
            setattr(citizen, f, v[f])
    if v.get("education") is not None:
        citizen.education = v["education"]
    citizen.field_provenance = merged.provenance
    citizen.source_status = report.source_status
    citizen.quality_status = report.overall
    citizen.last_synced_at = clock.now()
    return citizen


def _replace_issues(db: Session, citizen_id: str, application_id: uuid.UUID | None, report: QualityReport) -> None:
    now = clock.now()
    for issue in db.scalars(select(DataQualityIssue).where(
        DataQualityIssue.citizen_id == citizen_id,
        DataQualityIssue.status == "OPEN",
        DataQualityIssue.issue_type != DQIssueType.SOURCE_UNAVAILABLE,
    )):
        issue.status = "RESOLVED"
        issue.resolved_at = now
        issue.resolved_by = "SYSTEM:revalidation"
    for issue in report.issues:
        if issue.issue_type == DQIssueType.SOURCE_UNAVAILABLE:
            continue
        db.add(DataQualityIssue(
            citizen_id=citizen_id, application_id=application_id, source_system=issue.source_system,
            issue_type=issue.issue_type, severity=issue.severity, field=issue.field, message=issue.message,
            details=issue.details, status="OPEN",
        ))


def _open_issue(db: Session, citizen_id: str, application_id: uuid.UUID | None, system: str, issue_type: str, severity: str, message: str) -> None:
    existing = db.scalar(select(DataQualityIssue).where(
        DataQualityIssue.citizen_id == citizen_id, DataQualityIssue.source_system == system,
        DataQualityIssue.issue_type == issue_type, DataQualityIssue.status == "OPEN",
    ))
    if existing:
        existing.message = message
        existing.details = {**(existing.details or {}), "last_seen": clock.now().isoformat(), "occurrences": int((existing.details or {}).get("occurrences", 1)) + 1}
        return
    db.add(DataQualityIssue(citizen_id=citizen_id, application_id=application_id, source_system=system, issue_type=issue_type,
                            severity=severity, message=message, details={"occurrences": 1}, status="OPEN"))


def _resolve_availability_issues(db: Session, citizen_id: str, system: str) -> None:
    for issue in db.scalars(select(DataQualityIssue).where(
        DataQualityIssue.citizen_id == citizen_id, DataQualityIssue.source_system == system,
        DataQualityIssue.issue_type.in_([DQIssueType.SOURCE_UNAVAILABLE, DQIssueType.INVALID_RESPONSE]), DataQualityIssue.status == "OPEN",
    )):
        issue.status = "RESOLVED"
        issue.resolved_at = clock.now()
        issue.resolved_by = "SYSTEM:source-recovered"


def refresh_own_profile(db: Session, citizen_id: str, actor_name: str) -> tuple[MergedProfile, QualityReport, dict[str, str]]:
    """Citizen self-service: pull their records from every source that provides citizen data."""
    outputs, unavailable = [], {}
    for row in db.scalars(select(Connector).order_by(Connector.name)):
        if "get_citizen" not in row.capabilities or not row.data_categories:
            continue
        category = row.data_categories[0]
        try:
            result = fetch_category(db, citizen_id=citizen_id, category=category, connector_key=row.key, purpose="Self-service view",
                                    requester_department_id=None, requester_name=actor_name, self_access=True)
            outputs.append(result.to_output())
        except ConnectorError as exc:
            unavailable[row.system_name] = exc.message
    merged, report = consolidate(db, citizen_id, outputs, unavailable=unavailable)
    return merged, report, unavailable
