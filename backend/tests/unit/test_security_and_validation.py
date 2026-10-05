"""RBAC, JWT validation, request-schema validation, workflow definition validation, circuit breaker."""
from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from app.core.errors import AuthenticationError, ForbiddenError
from app.core.security import Principal, Role, decode_token, principal_from_claims
from app.schemas.requests import ApplicationCreate, ConsentCreate, GrievanceCreate
from app.workflow.engine import validate_definition


# ------------------------------------------------------------------ JWT / RBAC

def test_valid_token_maps_to_principal(token):
    p = principal_from_claims(decode_token(token("officer1")))
    assert p.roles == {Role.OFFICER}
    assert p.department_code == "SKILL_DEV"
    assert p.primary_role == Role.OFFICER


def test_expired_token_rejected(token):
    with pytest.raises(AuthenticationError) as exc:
        decode_token(token("citizen1", exp=int(time.time()) - 120, iat=int(time.time()) - 900))
    assert exc.value.code == "TOKEN_EXPIRED"


def test_wrong_audience_and_issuer_rejected(token):
    with pytest.raises(AuthenticationError):
        decode_token(token("citizen1", aud="some-other-api"))
    with pytest.raises(AuthenticationError):
        decode_token(token("citizen1", iss="http://evil/realms/x"))


def test_tampered_token_rejected(token):
    t = token("citizen1")
    head, body, sig = t.split(".")
    with pytest.raises(AuthenticationError):
        decode_token(f"{head}.{body}.{sig[::-1]}")


def test_account_without_platform_role_is_forbidden():
    with pytest.raises(ForbiddenError):
        principal_from_claims({"sub": "x", "realm_access": {"roles": ["offline_access"]}})


def test_role_precedence_and_staff_flags():
    p = Principal(subject="s", username="u", roles={Role.OFFICER, Role.DEPARTMENT_ADMIN})
    assert p.primary_role == Role.DEPARTMENT_ADMIN and p.is_staff and not p.is_platform_admin
    assert not Principal(subject="s", username="c", roles={Role.CITIZEN}).is_staff


def test_require_roles_dependency():
    from app.api.deps import require_roles

    checker = require_roles(Role.PLATFORM_ADMIN)
    with pytest.raises(ForbiddenError):
        checker(Principal(subject="s", username="o", roles={Role.OFFICER}))
    assert checker(Principal(subject="s", username="a", roles={Role.PLATFORM_ADMIN})).username == "a"


def test_application_role_scoping():
    from types import SimpleNamespace

    from app.services.application_service import authorize_officer, authorize_view

    app = SimpleNamespace(citizen_id="100001", department=SimpleNamespace(code="SKILL_DEV"))
    authorize_view(Principal(subject="s", username="c", roles={Role.CITIZEN}, citizen_id="100001"), app)
    with pytest.raises(ForbiddenError):
        authorize_view(Principal(subject="s", username="c2", roles={Role.CITIZEN}, citizen_id="100002"), app)
    with pytest.raises(ForbiddenError):
        authorize_officer(Principal(subject="s", username="o2", roles={Role.OFFICER}, department_code="GRIEVANCE_CELL"), app)
    with pytest.raises(ForbiddenError):  # admins cannot take department decisions
        authorize_officer(Principal(subject="s", username="a", roles={Role.PLATFORM_ADMIN}), app)


# ------------------------------------------------------------------ API validation

def test_application_request_validation():
    ApplicationCreate(service_code="SKILL_DEV_SCHEME", form_data={"preferred_trade": "ELECTRICIAN"})
    with pytest.raises(ValidationError):
        ApplicationCreate(service_code="skill dev; drop table", form_data={})
    with pytest.raises(ValidationError):
        ApplicationCreate(service_code="SKILL_DEV_SCHEME", form_data={"x": {"nested": "object"}})
    with pytest.raises(ValidationError):
        ApplicationCreate(service_code="SKILL_DEV_SCHEME", form_data={}, unexpected=True)


def test_consent_and_grievance_validation():
    with pytest.raises(ValidationError):
        ConsentCreate(application_id="not-a-uuid", data_categories=["IDENTITY"])
    with pytest.raises(ValidationError):
        ConsentCreate(application_id="6f1c2a10-0000-4000-8000-000000100001", data_categories=["BANK_ACCOUNTS"])
    with pytest.raises(ValidationError):
        GrievanceCreate(category="OTHER", subject="hi", description="too short")


def test_service_form_validation():
    from types import SimpleNamespace

    from app.core.errors import DomainValidationError
    from app.services.application_service import validate_form

    svc = SimpleNamespace(form_schema={"fields": [
        {"name": "trade", "type": "select", "required": True, "options": [{"value": "A"}, {"value": "B"}]},
        {"name": "note", "type": "text", "required": False, "maxLength": 5},
    ]})
    assert validate_form(svc, {"trade": "A"}) == {"trade": "A"}
    for bad in ({}, {"trade": "Z"}, {"trade": "A", "note": "toolong"}, {"trade": "A", "extra": "x"}):
        with pytest.raises(DomainValidationError):
            validate_form(svc, bad)


# ------------------------------------------------------------------ workflow definitions

def test_workflow_definition_validation():
    validate_definition({"steps": [{"key": "A", "type": "start"}, {"key": "B", "type": "fetch", "connector": "identity", "category": "IDENTITY"}]})
    for bad in (
        {"steps": []},
        {"steps": [{"key": "A", "type": "start"}, {"key": "A", "type": "decision"}]},
        {"steps": [{"key": "A", "type": "teleport"}]},
        {"steps": [{"key": "A", "type": "fetch"}]},
    ):
        with pytest.raises(ValueError):
            validate_definition(bad)


# ------------------------------------------------------------------ circuit breaker

def test_circuit_breaker_opens_and_recovers(monkeypatch):
    import app.integration.circuit_breaker as cbmod

    def no_redis():
        raise ConnectionError("redis unavailable in unit tests")

    monkeypatch.setattr(cbmod, "get_redis", no_redis)
    cb = cbmod.CircuitBreaker("unit-test", failure_threshold=2, open_seconds=1)
    assert cb.state == "CLOSED"
    cb.record_failure()
    assert cb.allow()
    cb.record_failure()
    assert cb.state == "OPEN" and not cb.allow()
    time.sleep(1.1)
    assert cb.state == "HALF_OPEN" and cb.allow()
    cb.record_success()
    assert cb.state == "CLOSED"
