"""Survivorship rules: merge per-source fragments into one golden record with provenance."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.mdm.canonical import CanonicalFragment

# Which source category is authoritative for each canonical field (first wins).
FIELD_AUTHORITY: dict[str, list[str]] = {
    "full_name": ["IDENTITY", "EDUCATION", "EMPLOYMENT"],
    "date_of_birth": ["IDENTITY", "EDUCATION", "EMPLOYMENT"],
    "gender": ["IDENTITY"],
    "mobile": ["IDENTITY"],
    "email": ["IDENTITY"],
    "address": ["IDENTITY"],
    "district": ["IDENTITY"],
    "state": ["IDENTITY"],
    "pincode": ["IDENTITY"],
    "education": ["EDUCATION"],
    "employment_status": ["EMPLOYMENT"],
    "employment": ["EMPLOYMENT"],
}


@dataclass
class SourceFragment:
    category: str
    connector_key: str
    system_name: str
    fragment: CanonicalFragment
    source_updated_at: str | None = None
    source_reference: str | None = None


@dataclass
class MergedProfile:
    citizen_id: str
    values: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"citizen_id": self.citizen_id, **self.values, "provenance": self.provenance}


def merge_fragments(citizen_id: str, fragments: list[SourceFragment]) -> MergedProfile:
    by_category = {f.category: f for f in fragments}
    merged = MergedProfile(citizen_id=citizen_id)
    for field_name, authorities in FIELD_AUTHORITY.items():
        for category in authorities:
            src = by_category.get(category)
            if not src:
                continue
            value = getattr(src.fragment, field_name, None)
            if value in (None, "", []):
                continue
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            merged.values[field_name] = value
            merged.provenance[field_name] = {"source": src.system_name, "connector": src.connector_key, "category": category}
            break
    return merged
