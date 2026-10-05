from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import any_user
from app.core.security import Principal

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", summary="Current user profile and roles (from the validated OIDC token)")
def me(principal: Principal = Depends(any_user)) -> dict:
    return {
        "subject": principal.subject,
        "username": principal.username,
        "name": principal.name,
        "email": principal.email,
        "roles": sorted(r.value for r in principal.roles),
        "primary_role": principal.primary_role.value,
        "citizen_id": principal.citizen_id,
        "department_code": principal.department_code,
    }
