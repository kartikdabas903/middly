"""Reference data: departments, services, workflow definitions, rules, connectors, roles, demo users."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Department, Service, User, WorkflowDefinition
from app.services import connector_service
from app.services.data_access_service import ensure_citizen
from app.services.user_service import ensure_roles
from app.workflow.engine import validate_definition

logger = logging.getLogger(__name__)

# Fixed ids so they match the Keycloak realm import (infrastructure/keycloak/realm-middly.json).
DEMO_USERS = [
    {"id": "6f1c2a10-0000-4000-8000-000000100001", "username": "citizen1", "name": "Rahul Sharma", "roles": ["CITIZEN"], "citizen_id": "100001"},
    {"id": "6f1c2a10-0000-4000-8000-000000100002", "username": "citizen2", "name": "Priya Deshmukh", "roles": ["CITIZEN"], "citizen_id": "100002"},
    {"id": "6f1c2a10-0000-4000-8000-000000100003", "username": "citizen3", "name": "Amit Verma", "roles": ["CITIZEN"], "citizen_id": "100003"},
    {"id": "6f1c2a10-0000-4000-8000-000000100004", "username": "citizen4", "name": "Sneha Patil", "roles": ["CITIZEN"], "citizen_id": "100004"},
    {"id": "6f1c2a10-0000-4000-8000-0000000a0001", "username": "officer1", "name": "Anjali Kulkarni", "roles": ["OFFICER"], "department": "SKILL_DEV"},
    {"id": "6f1c2a10-0000-4000-8000-0000000a0002", "username": "officer2", "name": "Vikram Joshi", "roles": ["OFFICER"], "department": "GRIEVANCE_CELL"},
    {"id": "6f1c2a10-0000-4000-8000-0000000b0001", "username": "deptadmin1", "name": "Meera Iyer", "roles": ["DEPARTMENT_ADMIN", "OFFICER"], "department": "SKILL_DEV"},
    {"id": "6f1c2a10-0000-4000-8000-0000000c0001", "username": "admin1", "name": "Platform Administrator", "roles": ["PLATFORM_ADMIN"]},
]

DEMO_CITIZEN_IDS = ["100001", "100002", "100003", "100004", "100005"]


def _config_dir() -> Path:
    return Path(get_settings().workflow_config_path)


def load_workflows(db: Session) -> None:
    for path in sorted((_config_dir() / "definitions").glob("*.json")):
        definition = json.loads(path.read_text(encoding="utf-8"))
        validate_definition(definition)
        row = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == definition["code"], WorkflowDefinition.version == definition["version"]))
        if row is None:
            row = WorkflowDefinition(code=definition["code"], version=definition["version"])
            db.add(row)
        row.name = definition["name"]
        row.description = definition.get("description", "")
        row.definition = definition
        row.is_active = True
    db.flush()


def load_departments_and_services(db: Session) -> None:
    catalog = json.loads((_config_dir() / "services.json").read_text(encoding="utf-8"))
    departments: dict[str, Department] = {}
    for d in catalog["departments"]:
        row = db.scalar(select(Department).where(Department.code == d["code"]))
        if row is None:
            row = Department(code=d["code"])
            db.add(row)
        row.name, row.description, row.is_demo = d["name"], d["description"], True
        departments[d["code"]] = row
    db.flush()
    for s in catalog["services"]:
        row = db.scalar(select(Service).where(Service.code == s["code"]))
        if row is None:
            row = Service(code=s["code"])
            db.add(row)
        rules = None
        if s.get("eligibility_rules_file"):
            rules = json.loads((_config_dir() / s["eligibility_rules_file"]).read_text(encoding="utf-8"))
        row.name = s["name"]
        row.description = s["description"]
        row.department_id = departments[s["department"]].id
        row.workflow_code = s["workflow"]
        row.department_connector_key = s.get("department_connector")
        row.required_categories = s["required_categories"]
        row.consent_purpose = s["consent_purpose"]
        row.consent_validity_days = s["consent_validity_days"]
        row.eligibility_rules = rules
        row.form_schema = s["form_schema"]
        row.is_active = True
    db.flush()


def load_users(db: Session) -> None:
    roles = ensure_roles(db)
    depts = {d.code: d.id for d in db.scalars(select(Department)).all()}
    for u in DEMO_USERS:
        if u.get("citizen_id"):
            ensure_citizen(db, u["citizen_id"])
        user = db.get(User, uuid.UUID(u["id"]))
        if user is None:
            user = User(id=uuid.UUID(u["id"]), username=u["username"])
            db.add(user)
        user.full_name = u["name"]
        user.email = f"{u['username']}@demo.middly.example"
        user.citizen_id = u.get("citizen_id")
        user.department_id = depts.get(u.get("department", ""))
        user.roles = [roles[r] for r in u["roles"]]
    db.flush()


def seed_reference_data(db: Session) -> None:
    ensure_roles(db)
    load_departments_and_services(db)
    load_workflows(db)
    connector_service.sync_registry(db)
    for cid in DEMO_CITIZEN_IDS:
        ensure_citizen(db, cid)
    load_users(db)
    db.commit()
    logger.info("Reference data loaded")
