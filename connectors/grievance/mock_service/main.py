"""DEMO / MOCK Public Grievance system.

Tickets progress inside the department system (RECEIVED -> ASSIGNED ->
IN_PROGRESS) on their own; resolution is recorded by the department through
`/grievances/{id}/status`. The platform only *reads* this status — it never
edits department records. Auth: OAuth2 client credentials.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

from mock_common.mock_app import DocumentStore, OAuthClientCredentials, _admin_guard, create_mock_app

store = DocumentStore(Path(os.environ.get("MOCK_RUNTIME_DIR", "/tmp/mock-runtime")) / "grievance.sqlite3")
oauth = OAuthClientCredentials("GRIEVANCE_CLIENT_ID", "GRIEVANCE_CLIENT_SECRET")

app = create_mock_app(
    code="mock-grievance",
    title="Public Grievance Redressal System",
    description="Grievance ticketing system (demo). Uses OAuth2 client credentials.",
    reset_hook=store.clear,
)
oauth.mount(app, "/grievances/oauth/token")

AUTO_PROGRESS = [(0, "RECEIVED", None), (30, "ASSIGNED", "Assigned to Grievance Desk Officer (Demo)"), (120, "IN_PROGRESS", "Under examination by department")]
STATES = {"RECEIVED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"}


class GrievanceIn(BaseModel):
    citizen_ref: str = Field(..., max_length=20)
    category: str = Field(..., max_length=60)
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    platform_reference: str = Field(..., max_length=40)


class StatusIn(BaseModel):
    state: str
    remarks: str | None = None


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _materialize(record: dict) -> dict:
    """Apply time-based auto progression unless the department set the state explicitly."""
    if record.get("manual_state"):
        return record
    age = time.time() - record["created_ts"]
    for threshold, state, remark in AUTO_PROGRESS:
        if age >= threshold and _rank(state) > _rank(record["state"]):
            record["state"] = state
            record["history"].append({"state": state, "at": _iso(record["created_ts"] + threshold), "remarks": remark})
            if state == "ASSIGNED":
                record["assigned_to"] = "Grievance Desk Officer (Demo)"
    return record


def _rank(state: str) -> int:
    order = ["RECEIVED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    return order.index(state) if state in order else 99


@app.post("/grievances", status_code=201, dependencies=[Depends(oauth.guard)], tags=["grievance"])
def create_grievance(body: GrievanceIn):
    for existing in store.all():
        if existing["platform_reference"] == body.platform_reference:
            return _public(existing)
    seq = store.next_value("ticket")
    ticket = f"GRV-{datetime.now(timezone.utc).year}-{seq:05d}"
    now = time.time()
    record = {
        "ticketNo": ticket,
        **body.model_dump(),
        "state": "RECEIVED",
        "assigned_to": None,
        "manual_state": False,
        "created_ts": now,
        "history": [{"state": "RECEIVED", "at": _iso(now), "remarks": "Grievance registered"}],
    }
    store.put(ticket, record)
    return _public(record)


@app.get("/grievances/{ticket_no}", dependencies=[Depends(oauth.guard)], tags=["grievance"])
def get_grievance(ticket_no: str):
    record = store.get(ticket_no)
    if not record:
        raise HTTPException(status_code=404, detail="Ticket not found")
    record = _materialize(record)
    store.put(ticket_no, record)
    return _public(record)


@app.post("/grievances/{ticket_no}/status", tags=["grievance"])
def update_status(ticket_no: str, body: StatusIn, x_admin_key: str | None = Header(default=None)):
    """Department-side update (used by the department's own staff; demo-admin key protected)."""
    _admin_guard(x_admin_key)
    record = store.get(ticket_no)
    if not record:
        raise HTTPException(status_code=404, detail="Ticket not found")
    state = body.state.upper()
    if state not in STATES:
        raise HTTPException(status_code=422, detail=f"state must be one of {sorted(STATES)}")
    record["state"] = state
    record["manual_state"] = True
    record["history"].append({"state": state, "at": _iso(time.time()), "remarks": body.remarks})
    store.put(ticket_no, record)
    return _public(record)


def _public(record: dict) -> dict:
    return {
        "ticketNo": record["ticketNo"],
        "state": record["state"],
        "category": record["category"],
        "subject": record["subject"],
        "assignedTo": record.get("assigned_to"),
        "platformReference": record["platform_reference"],
        "createdAt": _iso(record["created_ts"]),
        "history": record["history"],
    }
