"""DEMO / MOCK Education Registry.

Format quirks (intentional): snake_case, `student_name` instead of full name,
YYYY/MM/DD dates, upper-case names, a list of qualifications instead of a single
"highest qualification", response wrapped in a registry envelope. Auth: API key.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, HTTPException

from mock_common.mock_app import api_key_auth, create_mock_app, load_json

DATA = Path(__file__).parent / "data" / "students.json"

app = create_mock_app(
    code="mock-education",
    title="Education Registry",
    description="Academic qualification records. Uses a static API key (X-API-Key).",
)

_records = {r["citizen_ref"]: r for r in load_json(DATA)}
_guard = api_key_auth("EDUCATION_API_KEY")


@app.get("/education/citizens/{citizen_id}", dependencies=[Depends(_guard)], tags=["education"])
def get_student(citizen_id: str):
    record = _records.get(citizen_id)
    if not record:
        raise HTTPException(status_code=404, detail="Student record not found")
    return {"registry": "Education Registry (DEMO)", "schema_version": "2.3", "record": record}
