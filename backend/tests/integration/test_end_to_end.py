"""Integration: citizen -> consent -> data aggregation -> eligibility -> application ->
officer approval -> event -> notification, plus outage/retry, consent enforcement and RBAC.

Uses the real database, Redis and mock department systems; events are dispatched
in-process (EVENT_DISPATCH_MODE=inline) with the same consumer handlers the worker runs.
"""
from __future__ import annotations

import pytest

from app.integration.errors import SourceUnavailableError
from app.integration.registry import registry

CATEGORIES = ["IDENTITY", "EDUCATION", "EMPLOYMENT"]
FORM = {"preferred_trade": "ELECTRICIAN", "preferred_district": "Pune", "training_mode": "CLASSROOM"}


def apply(client, auth, user, form=FORM):
    r = client.post("/api/v1/applications", json={"service_code": "SKILL_DEV_SCHEME", "form_data": form}, headers=auth(user))
    assert r.status_code == 201, r.text
    return r.json()


def consent(client, auth, user, app_id, categories=CATEGORIES):
    return client.post("/api/v1/consents", json={"application_id": app_id, "data_categories": categories}, headers=auth(user))


def test_successful_cross_department_flow(client, auth):
    app = apply(client, auth, "citizen1")
    assert app["status"] == "CONSENT_PENDING"
    assert app["consent_request"]["categories"] == CATEGORIES
    assert app["permissions"]["can_grant_consent"]

    # Data access before consent is impossible.
    early = client.post(f"/api/v1/applications/{app['id']}/process", headers=auth("citizen1")).json()
    assert early["status"] == "CONSENT_PENDING"

    assert consent(client, auth, "citizen1", app["id"]).status_code == 201
    done = client.post(f"/api/v1/applications/{app['id']}/process", headers=auth("citizen1")).json()
    assert done["status"] == "UNDER_REVIEW", done["workflow"]
    assert all(s["state"] == "VERIFIED" for s in done["sources"])
    assert done["eligibility"]["eligible"] is True
    profile = done["profile"]
    assert profile["full_name"] == "Rahul Sharma"                     # normalised from fullName / student_name / candidateName
    assert profile["state"] == "Maharashtra"                         # from state code MH
    assert profile["employment_status"] == "UNEMPLOYED"
    assert profile["provenance"]["education"]["source"] == "Education Registry"
    assert done["department_reference"].startswith("SKL-")

    # Officer from another department cannot see it; the right officer can.
    assert client.get(f"/api/v1/applications/{app['id']}", headers=auth("officer2")).status_code == 403
    queue = client.get("/api/v1/applications?status=UNDER_REVIEW", headers=auth("officer1")).json()
    assert app["id"] in [a["id"] for a in queue["items"]]
    officer_view = client.get(f"/api/v1/applications/{app['id']}", headers=auth("officer1")).json()
    assert officer_view["profile"]["full_name"] == "Rahul Sharma"
    assert officer_view["permissions"]["can_decide"]

    # Citizens cannot approve their own application.
    assert client.post(f"/api/v1/applications/{app['id']}/approve", json={}, headers=auth("citizen1")).status_code == 403

    approved = client.post(f"/api/v1/applications/{app['id']}/approve", json={"remarks": "Verified"}, headers=auth("officer1")).json()
    assert approved["status"] == "APPROVED"

    # Event -> notification consumer -> workflow completes.
    final = client.get(f"/api/v1/applications/{app['id']}", headers=auth("citizen1")).json()
    assert final["workflow"]["status"] == "COMPLETED"
    assert all(s["state"] in ("done", "skipped") for s in final["timeline"])
    notes = client.get("/api/v1/notifications", headers=auth("citizen1")).json()["items"]
    assert any(n["message"].startswith(f"Application {app['application_number']} approved.") for n in notes)

    events = client.get(f"/api/v1/events?aggregate_id={app['id']}&limit=100", headers=auth("admin1")).json()["items"]
    types = {e["event_type"] for e in events}
    assert {"APPLICATION_CREATED", "DATA_FETCHED", "ELIGIBILITY_COMPLETED", "APPLICATION_SUBMITTED", "APPLICATION_APPROVED"} <= types
    approved_evt = next(e for e in events if e["event_type"] == "APPLICATION_APPROVED")
    assert {"notification-dispatcher", "department-sync"} <= set(approved_evt["processed_by"])

    audit = client.get(f"/api/v1/audit-logs?resource_id={app['id']}&limit=200", headers=auth("admin1")).json()["items"]
    actions = {a["action"] for a in audit}
    assert {"CITIZEN_SUBMITTED_APPLICATION", "OFFICER_VIEWED_APPLICATION", "OFFICER_APPROVED_APPLICATION"} <= actions
    assert client.get("/api/v1/audit-logs/verify", headers=auth("admin1")).json()["valid"] is True

    overview = client.get("/api/v1/admin/overview", headers=auth("admin1")).json()
    assert overview["connector_calls"]["total"] >= 4
    assert overview["avg_processing_seconds"] is not None


def test_eligibility_failure_auto_rejects_with_reasons(client, auth):
    app = apply(client, auth, "citizen3", {**FORM, "preferred_district": "Nagpur"})
    consent(client, auth, "citizen3", app["id"])
    done = client.post(f"/api/v1/applications/{app['id']}/process", headers=auth("citizen3")).json()
    assert done["status"] == "REJECTED"
    assert set(done["eligibility"]["failed_rules"]) == {"MAHARASHTRA_RESIDENT", "AGE_RANGE", "EMPLOYMENT_REQUIREMENT"}
    assert done["data_quality_report"]["overall"] == "CONFLICT"   # Verma/Varma + DOB mismatch
    officer_review = next(s for s in done["timeline"] if s["key"] == "OFFICER_REVIEW")
    assert officer_review["status"] == "SKIPPED"
    notes = client.get("/api/v1/notifications", headers=auth("citizen3")).json()["items"]
    assert any("was not approved" in n["message"] for n in notes)


def test_department_outage_waits_and_retry_resumes(client, auth, monkeypatch):
    original = registry.get_class("employment")

    class DownEmployment(original):  # type: ignore[misc, valid-type]
        def get_citizen(self, citizen_id):
            raise SourceUnavailableError("Employment Registry unavailable (HTTP 503)", http_status=503)

    monkeypatch.setitem(registry._classes, "employment", DownEmployment)
    app = apply(client, auth, "citizen2", {**FORM, "preferred_district": "Nagpur"})
    consent(client, auth, "citizen2", app["id"])
    waiting = client.post(f"/api/v1/applications/{app['id']}/process", headers=auth("citizen2")).json()
    assert waiting["status"] == "WAITING_FOR_SOURCE"
    assert waiting["workflow"]["status"] == "WAITING_FOR_SOURCE"
    assert waiting["permissions"]["can_retry"]
    employment = next(s for s in waiting["sources"] if s["category"] == "EMPLOYMENT")
    assert employment["state"] == "UNAVAILABLE"
    identity = next(s for s in waiting["sources"] if s["category"] == "IDENTITY")
    assert identity["state"] == "VERIFIED"  # completed steps are not repeated

    monkeypatch.setitem(registry._classes, "employment", original)
    resumed = client.post(f"/api/v1/applications/{app['id']}/retry", headers=auth("citizen2")).json()
    assert resumed["status"] == "UNDER_REVIEW"
    assert all(s["state"] == "VERIFIED" for s in resumed["sources"])

    # Consent enforcement: revoke -> officer loses visibility and cannot approve.
    consent_id = resumed["consent"]["consent_id"]
    assert client.post(f"/api/v1/consents/{consent_id}/revoke", json={"reason": "test"}, headers=auth("citizen2")).status_code == 200
    officer_view = client.get(f"/api/v1/applications/{app['id']}", headers=auth("officer1")).json()
    assert officer_view["profile"] is None
    blocked = client.post(f"/api/v1/applications/{app['id']}/approve", json={}, headers=auth("officer1"))
    assert blocked.status_code == 409
    profile_access = client.get("/api/v1/citizens/100002/profile", headers=auth("officer1"))
    assert profile_access.status_code == 403 and profile_access.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_consent_rules(client, auth):
    app = apply(client, auth, "citizen1", {**FORM, "training_mode": "ONLINE"})
    # Partial consent is refused for required categories.
    partial = consent(client, auth, "citizen1", app["id"], ["IDENTITY"])
    assert partial.status_code == 422
    # Someone else cannot consent on the citizen's behalf.
    assert consent(client, auth, "citizen2", app["id"]).status_code == 403
    # Duplicate active application for the same service is rejected.
    dup = client.post("/api/v1/applications", json={"service_code": "SKILL_DEV_SCHEME", "form_data": FORM}, headers=auth("citizen1"))
    assert dup.status_code == 409
    # Withdraw closes it.
    w = client.post(f"/api/v1/applications/{app['id']}/withdraw", json={"reason": "test"}, headers=auth("citizen1")).json()
    assert w["status"] == "WITHDRAWN"


@pytest.mark.parametrize(
    "user,path,expected",
    [
        ("citizen1", "/api/v1/admin/overview", 403),
        ("citizen1", "/api/v1/audit-logs", 403),
        ("officer1", "/api/v1/audit-logs", 403),
        ("officer1", "/api/v1/connectors", 403),
        ("admin1", "/api/v1/connectors", 200),
        ("admin1", "/api/v1/workflows/definitions", 200),
    ],
)
def test_rbac_matrix(client, auth, user, path, expected):
    assert client.get(path, headers=auth(user)).status_code == expected


def test_authentication_and_validation_errors(client, auth):
    assert client.get("/api/v1/applications").status_code == 401
    r = client.get("/api/v1/applications", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    bad = client.post("/api/v1/applications", json={"service_code": "SKILL_DEV_SCHEME", "form_data": {"preferred_trade": "ASTRONAUT"}}, headers=auth("citizen1"))
    assert bad.status_code == 422
    # Correlation id is echoed back
    r = client.get("/api/v1/services", headers={"X-Request-ID": "corr-abc-123"})
    assert r.headers["X-Request-ID"] == "corr-abc-123"


def test_grievance_is_tracked_from_department_system(client, auth):
    r = client.post("/api/v1/grievances", json={"category": "SERVICE_DELAY", "subject": "Delay in stipend", "description": "Stipend not credited for two months."},
                    headers=auth("citizen1"))
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["department_reference"].startswith("GRV-")
    assert g["workflow"]["status"] == "WAITING_FOR_EXTERNAL"
    resolved = client.post(f"/api/v1/demo/grievances/{g['id']}/resolve", headers=auth("admin1")).json()
    assert resolved["status"] == "RESOLVED"
