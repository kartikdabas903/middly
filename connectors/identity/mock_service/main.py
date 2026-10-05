"""DEMO / MOCK Identity Service.

Format quirks (intentional): camelCase fields, DD-MM-YYYY dates, single-letter
gender codes, state codes, free-form phone numbers. Auth: OAuth2 client credentials.
Identifiers such as `aadhaarRef` are clearly fake demo references.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, HTTPException

from mock_common.mock_app import OAuthClientCredentials, create_mock_app, load_json

DATA = Path(__file__).parent / "data" / "citizens.json"
oauth = OAuthClientCredentials("IDENTITY_CLIENT_ID", "IDENTITY_CLIENT_SECRET")

app = create_mock_app(
    code="mock-identity",
    title="Identity Service",
    description="Resident identity registry. Uses OAuth2 client credentials.",
)
oauth.mount(app, "/identity/oauth/token")

_records = {r["citizenId"]: r for r in load_json(DATA)}


@app.get("/identity/citizens/{citizen_id}", dependencies=[Depends(oauth.guard)], tags=["identity"])
def get_citizen(citizen_id: str):
    record = _records.get(citizen_id)
    if not record:
        raise HTTPException(status_code=404, detail="No resident with this identifier")
    return record
