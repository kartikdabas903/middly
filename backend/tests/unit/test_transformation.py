"""Connector transformation + canonical validation + normalisation helpers."""
from __future__ import annotations

import pytest

from app.integration.errors import InvalidSourceResponseError
from app.integration.normalize import (
    mask_mobile,
    name_similarity,
    names_compatible,
    normalize_employment_status,
    normalize_mobile,
    normalize_name,
    normalize_state,
    parse_date,
    qualification_level,
)
from app.integration.registry import ConnectorRegistry
from app.integration.sdk import ConnectorConfig
from app.mdm.canonical import validate_fragment
from app.mdm.merge import SourceFragment, merge_fragments


@pytest.fixture(scope="module")
def connectors():
    import os

    reg = ConnectorRegistry()
    reg.discover(os.environ["CONNECTORS_PATH"])
    return reg


def build(reg, key):
    cls = reg.get_class(key)
    return cls(ConnectorConfig(key=key, base_url="http://unused", credentials={}))


def test_plugins_discovered_without_core_changes(connectors):
    assert {"identity", "education", "employment", "skill", "grievance"} <= set(connectors.all())


def test_identity_transform_maps_camelcase_and_drops_aadhaar(connectors):
    raw = {
        "citizenId": "100001", "aadhaarRef": "DEMO-XXXX-XXXX-1001", "fullName": "RAHUL SHARMA", "dob": "14-03-2002",
        "gender": "M", "mobileNumber": "+91 90000 10001", "emailId": "r@demo.example",
        "address": {"line1": "Flat 12", "district": "Pune", "stateCode": "MH", "pincode": "411005"},
        "lastUpdated": "2026-06-12T09:30:00Z",
    }
    rec = build(connectors, "identity").transform_response(raw, "citizen", citizen_id="100001")
    c = rec.canonical
    assert c["full_name"] == "Rahul Sharma"
    assert c["date_of_birth"] == "2002-03-14"
    assert c["gender"] == "MALE"
    assert c["state"] == "Maharashtra"
    assert c["mobile"] == "XXXXXX0001"
    assert "aadhaar" not in str(c).lower()


def test_education_transform_picks_highest_qualification(connectors):
    raw = {"record": {"citizen_ref": "100002", "student_name": "Priya Sunil Deshmukh", "date_of_birth": "2001/11/05",
                      "qualifications": [{"level": "SSC", "passing_year": 2017}, {"level": "Diploma", "passing_year": 2022, "institution": "X"}]}}
    rec = build(connectors, "education").transform_response(raw, "citizen", citizen_id="100002")
    assert rec.canonical["education"]["qualification_level"] == "DIPLOMA"
    assert rec.canonical["full_name"] == "Priya Sunil Deshmukh"
    assert rec.canonical["date_of_birth"] == "2001-11-05"


def test_employment_transform_maps_legacy_codes(connectors):
    raw = {"status": "OK", "data": {"citizenRef": "100003", "candidateName": "Amit Kumar Varma", "dateOfBirth": "1985-06-21", "employmentStatus": "EMP"}}
    rec = build(connectors, "employment").transform_response(raw, "citizen", citizen_id="100003")
    assert rec.canonical["employment_status"] == "EMPLOYED"


def test_invalid_source_envelope_is_rejected(connectors):
    with pytest.raises(InvalidSourceResponseError):
        build(connectors, "employment").transform_response({"status": "ERR"}, "citizen")
    with pytest.raises(InvalidSourceResponseError):
        build(connectors, "identity").transform_response({"unexpected": True}, "citizen")


def test_canonical_validation_drops_invalid_fields_and_reports_them():
    fragment, issues = validate_fragment({"citizen_id": "100001", "full_name": "Rahul Sharma", "pincode": "41100X", "email": "not-an-email"})
    assert fragment.full_name == "Rahul Sharma"
    assert fragment.pincode is None and fragment.email is None
    assert {i["field"] for i in issues} == {"pincode", "email"}


def test_canonical_validation_rejects_bad_citizen_id():
    with pytest.raises(Exception):
        validate_fragment({"citizen_id": "abc"})


def test_merge_uses_survivorship_and_records_provenance():
    ident, _ = validate_fragment({"citizen_id": "100001", "full_name": "Rahul Sharma", "state": "Maharashtra"})
    edu, _ = validate_fragment({"citizen_id": "100001", "full_name": "Rahul S", "education": {"highest_qualification": "B.Tech", "qualification_level": "GRADUATE"}})
    merged = merge_fragments("100001", [
        SourceFragment("EDUCATION", "education", "Education Registry", edu),
        SourceFragment("IDENTITY", "identity", "Identity Service", ident),
    ])
    assert merged.values["full_name"] == "Rahul Sharma"
    assert merged.provenance["full_name"]["source"] == "Identity Service"
    assert merged.provenance["education"]["source"] == "Education Registry"


@pytest.mark.parametrize(
    "value,expected",
    [("14-03-2002", "2002-03-14"), ("2002/03/14", "2002-03-14"), ("2002-03-14", "2002-03-14")],
)
def test_parse_date_formats(value, expected):
    assert parse_date(value).isoformat() == expected


def test_normalisers():
    assert normalize_name("  rahul   SHARMA ") == "Rahul Sharma"
    assert normalize_state("MP") == "Madhya Pradesh"
    assert normalize_mobile("+91 90000 10001") == "9000010001"
    assert mask_mobile("9000010001") == "XXXXXX0001"
    assert normalize_employment_status("UNEMP") == "UNEMPLOYED"
    assert qualification_level("B.Tech") == "GRADUATE"
    assert names_compatible("Priya Deshmukh", "Priya Sunil Deshmukh")
    assert not names_compatible("Amit Verma", "Amit Kumar Varma")
    assert name_similarity("Amit Verma", "Amit Varma") > 0.8
