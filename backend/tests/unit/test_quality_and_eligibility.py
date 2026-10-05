from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.eligibility.engine import evaluate
from app.mdm.canonical import validate_fragment
from app.mdm.merge import SourceFragment
from app.mdm.quality import evaluate_quality

RULES = json.loads((Path(os.environ["WORKFLOW_CONFIG_PATH"]) / "rules" / "skill_development_rules.json").read_text())


def frag(category, system, **fields):
    f, _ = validate_fragment({"citizen_id": "100003", **fields})
    return SourceFragment(category, category.lower(), system, f)


# ------------------------------------------------------------------ data quality

def test_name_and_dob_conflicts_are_flagged():
    report = evaluate_quality([
        frag("IDENTITY", "Identity Service", full_name="Amit Verma", date_of_birth="1985-06-21", gender="MALE", state="Madhya Pradesh", district="Indore"),
        frag("EDUCATION", "Education Registry", full_name="Amit Verma", date_of_birth="1985-12-06",
             education={"highest_qualification": "B.Com", "qualification_level": "GRADUATE"}),
        frag("EMPLOYMENT", "Employment Registry", full_name="Amit Kumar Varma", employment_status="EMPLOYED"),
    ])
    types = {i.issue_type for i in report.issues}
    assert {"DOB_CONFLICT", "NAME_CONFLICT"} <= types
    assert report.source_status["Identity Service"]["status"] == "CONFLICT"
    assert report.source_status["Identity Service"]["reason"] == "Name mismatch between systems"
    assert report.overall == "CONFLICT"


def test_middle_name_is_only_a_variation():
    report = evaluate_quality([
        frag("IDENTITY", "Identity Service", full_name="Priya Deshmukh", gender="FEMALE", state="Maharashtra", district="Nagpur", date_of_birth="2001-11-05"),
        frag("EDUCATION", "Education Registry", full_name="Priya Sunil Deshmukh", education={"highest_qualification": "Diploma", "qualification_level": "DIPLOMA"}),
    ])
    assert [i.issue_type for i in report.issues] == ["NAME_VARIATION"]
    assert report.source_status["Identity Service"]["status"] == "VERIFIED"


def test_missing_stale_duplicate_and_unavailable():
    old = SourceFragment("IDENTITY", "identity", "Identity Service",
                         validate_fragment({"citizen_id": "100004", "full_name": "Sneha Patil"})[0], source_updated_at="2023-01-15T00:00:00+00:00")
    report = evaluate_quality(
        [old],
        unavailable={"Employment Registry": "HTTP 503"},
        duplicate_candidates=[{"citizen_id": "100005", "district": "Sangli"}],
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    types = [i.issue_type for i in report.issues]
    assert "MISSING_FIELD" in types and "STALE_DATA" in types and "DUPLICATE_RECORD" in types and "SOURCE_UNAVAILABLE" in types
    assert report.source_status["Employment Registry"]["status"] == "UNAVAILABLE"
    assert report.overall == "UNAVAILABLE"


# ------------------------------------------------------------------ eligibility (DEMO rules)

ELIGIBLE = {"state": "Maharashtra", "date_of_birth": "2002-03-14", "education": {"qualification_level": "GRADUATE"}, "employment_status": "UNEMPLOYED"}


def test_eligible_profile_passes_all_demo_rules():
    r = evaluate(RULES, ELIGIBLE, on=date(2026, 10, 3))
    assert r.eligible and r.demo
    assert r.failed_rules == []
    assert r.passed_rules == ["MAHARASHTRA_RESIDENT", "AGE_RANGE", "EDUCATION_REQUIREMENT", "EMPLOYMENT_REQUIREMENT"]


def test_ineligible_profile_reports_failed_rules_and_reasons():
    profile = {"state": "Madhya Pradesh", "date_of_birth": "1985-06-21", "education": {"qualification_level": "GRADUATE"}, "employment_status": "EMPLOYED"}
    r = evaluate(RULES, profile, on=date(2026, 10, 3))
    assert not r.eligible
    assert r.failed_rules == ["MAHARASHTRA_RESIDENT", "AGE_RANGE", "EMPLOYMENT_REQUIREMENT"]
    assert len(r.reasons) == 3


@pytest.mark.parametrize("dob,ok", [("2008-10-04", False), ("2008-10-03", True), ("1990-10-04", True), ("1990-10-03", False)])
def test_age_boundaries(dob, ok):
    assert evaluate(RULES, {**ELIGIBLE, "date_of_birth": dob}, on=date(2026, 10, 3)).eligible is ok


def test_missing_data_fails_closed():
    r = evaluate(RULES, {"state": "Maharashtra"}, on=date(2026, 10, 3))
    assert not r.eligible
    assert "EDUCATION_REQUIREMENT" in r.failed_rules


def test_unknown_operator_is_rejected():
    with pytest.raises(ValueError):
        evaluate({"rules": [{"id": "X", "operator": "magic", "field": "state"}]}, {})
