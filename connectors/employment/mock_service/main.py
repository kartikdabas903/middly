"""DEMO / MOCK Employment Registry.

Format quirks (intentional): `{status, data}` envelope, camelCase, ISO dates,
legacy status codes (UNEMP / EMP / SALARIED). Auth: HTTP Basic.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends
from fastapi.responses import JSONResponse

from mock_common.mock_app import basic_auth, create_mock_app, load_json

DATA = Path(__file__).parent / "data" / "candidates.json"

app = create_mock_app(
    code="mock-employment",
    title="Employment Registry",
    description="Job-seeker and employment status registry. Uses HTTP Basic authentication.",
)

_records = {r["citizenRef"]: r for r in load_json(DATA)}
_guard = basic_auth("EMPLOYMENT_BASIC_USER", "EMPLOYMENT_BASIC_PASSWORD")


@app.get("/employment/citizens/{citizen_id}", dependencies=[Depends(_guard)], tags=["employment"])
def get_candidate(citizen_id: str):
    record = _records.get(citizen_id)
    if not record:
        return JSONResponse(status_code=404, content={"status": "NOT_FOUND", "data": None})
    return {"status": "OK", "data": record}
