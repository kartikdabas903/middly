from __future__ import annotations

from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import get_context
from app.core.errors import AuthenticationError, ForbiddenError
from app.core.security import Principal, Role, decode_token, principal_from_claims
from app.db.session import get_db
from app.services.user_service import provision

bearer = HTTPBearer(auto_error=False, description="Keycloak-issued access token (OIDC)")


def get_principal(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer token")
    principal = principal_from_claims(decode_token(creds.credentials))
    ctx = get_context()
    ctx.actor = principal.username
    ctx.actor_id = principal.subject
    ctx.role = principal.primary_role.value
    ctx.department_code = principal.department_code
    provision(db, principal)
    return principal


def require_roles(*roles: Role) -> Callable[..., Principal]:
    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_any(*roles):
            raise ForbiddenError(f"Requires one of roles: {', '.join(r.value for r in roles)}")
        return principal

    return checker


citizen_only = require_roles(Role.CITIZEN)
officer_roles = require_roles(Role.OFFICER, Role.DEPARTMENT_ADMIN)
admin_roles = require_roles(Role.PLATFORM_ADMIN, Role.DEPARTMENT_ADMIN)
platform_admin = require_roles(Role.PLATFORM_ADMIN)
any_user = get_principal
