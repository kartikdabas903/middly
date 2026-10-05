"""Just-in-time provisioning of local user records from validated OIDC tokens."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.redis import get_redis
from app.core.security import Principal
from app.models import Department, Role, User
from app.services.data_access_service import ensure_citizen

logger = logging.getLogger(__name__)

ROLE_DESCRIPTIONS = {
    "CITIZEN": "Citizen applying for services and managing consent",
    "OFFICER": "Department officer reviewing applications",
    "DEPARTMENT_ADMIN": "Department administrator",
    "PLATFORM_ADMIN": "Interoperability platform administrator",
}


def ensure_roles(db: Session) -> dict[str, Role]:
    roles = {r.code: r for r in db.scalars(select(Role)).all()}
    for code, desc in ROLE_DESCRIPTIONS.items():
        if code not in roles:
            roles[code] = Role(code=code, description=desc)
            db.add(roles[code])
    db.flush()
    return roles


def provision(db: Session, principal: Principal) -> None:
    cache_key = f"user:provisioned:{principal.subject}"
    try:
        if get_redis().get(cache_key):
            return
    except Exception:
        pass
    try:
        user_id = uuid.UUID(principal.subject)
    except ValueError:
        return
    user = db.get(User, user_id)
    if user is None:
        user = db.scalar(select(User).where(User.username == principal.username))
        if user is not None and user.id != user_id:
            # Identity provider was re-created: the username now maps to a new subject.
            db.delete(user)
            db.flush()
            user = None
    if user is None:
        user = User(id=user_id, username=principal.username)
        db.add(user)
    if principal.citizen_id:
        ensure_citizen(db, principal.citizen_id)
    user.full_name = principal.name
    user.email = principal.email
    user.citizen_id = principal.citizen_id
    user.department_id = db.scalar(select(Department.id).where(Department.code == principal.department_code)) if principal.department_code else None
    roles = ensure_roles(db)
    user.roles = [roles[r.value] for r in principal.roles if r.value in roles]
    user.last_login_at = clock.now()
    db.commit()
    try:
        get_redis().set(cache_key, "1", ex=600)
    except Exception:
        pass
