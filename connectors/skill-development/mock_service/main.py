"""DEMO / MOCK Skill Development Department system.

Receives applications forwarded by the platform and records the department's
decision. Format quirks: `enrolmentId`, `applicantRef`, PascalCase status codes.
Auth: API key in `X-Dept-Key` header.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from mock_common.mock_app import DocumentStore, api_key_auth, create_mock_app

store = DocumentStore(Path(os.environ.get("MOCK_RUNTIME_DIR", "/tmp/mock-runtime")) / "skill.sqlite3")

app = create_mock_app(
    code="mock-skill",
    title="Skill Development Department System",
    description="Training enrolment system of the Skill Development Department (demo). Uses an API key (X-Dept-Key).",
    reset_hook=store.clear,
)
_guard = api_key_auth("SKILL_API_KEY", header="X-Dept-Key")

BATCHES = {
    "ELECTRICIAN": "DEMO-ELEC",
    "SOFTWARE_DEVELOPMENT": "DEMO-SWD",
    "DATA_ENTRY": "DEMO-DEO",
    "ELECTRONICS_REPAIR": "DEMO-ELR",
    "RETAIL_SALES": "DEMO-RTL",
}


class SkillApplicationIn(BaseModel):
    applicantRef: str = Field(..., max_length=20)
    applicantName: str = Field(..., max_length=200)
    schemeCode: str = Field(..., max_length=60)
    platformReference: str = Field(..., max_length=40)
    preferredTrade: str = Field(..., max_length=60)
    preferredDistrict: str = Field(..., max_length=80)
    trainingMode: str = Field("CLASSROOM", max_length=20)
    eligibilityVerified: bool = False


class DecisionIn(BaseModel):
    decision: str
    remarks: str | None = None
    decidedBy: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.post("/skill/applications", status_code=201, dependencies=[Depends(_guard)], tags=["skill"])
def create_application(body: SkillApplicationIn):
    for existing in store.all():
        if existing["platformReference"] == body.platformReference:
            return existing  # idempotent on platform reference
    seq = store.next_value("enrolment")
    enrolment_id = f"SKL-{datetime.now(timezone.utc).year}-{seq:06d}"
    record = {
        "enrolmentId": enrolment_id,
        **body.model_dump(),
        "status": "Received",
        "batchCode": None,
        "remarks": None,
        "receivedAt": _now(),
        "updatedAt": _now(),
    }
    store.put(enrolment_id, record)
    return record


@app.get("/skill/applications/{enrolment_id}", dependencies=[Depends(_guard)], tags=["skill"])
def get_application(enrolment_id: str):
    record = store.get(enrolment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Enrolment not found")
    return record


@app.get("/skill/applications", dependencies=[Depends(_guard)], tags=["skill"])
def list_applications():
    return {"items": store.all()}


@app.post("/skill/applications/{enrolment_id}/decision", dependencies=[Depends(_guard)], tags=["skill"])
def record_decision(enrolment_id: str, body: DecisionIn):
    record = store.get(enrolment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Enrolment not found")
    decision = body.decision.upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=422, detail="decision must be APPROVED or REJECTED")
    record["status"] = "Sanctioned" if decision == "APPROVED" else "NotSanctioned"
    record["remarks"] = body.remarks
    record["decidedBy"] = body.decidedBy
    if decision == "APPROVED":
        prefix = BATCHES.get(record["preferredTrade"], "DEMO-GEN")
        record["batchCode"] = f"{prefix}-{record['preferredDistrict'][:3].upper()}-{datetime.now(timezone.utc):%y%m}"
    record["updatedAt"] = _now()
    store.put(enrolment_id, record)
    return record
