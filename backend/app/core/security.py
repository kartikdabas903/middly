"""OIDC/JWT validation and role-based access control.

Tokens are issued by Keycloak. The backend validates signature (JWKS), issuer,
audience and expiry, then maps realm roles to platform roles.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum

import httpx
import jwt
from jwt import PyJWKSet

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ForbiddenError

logger = logging.getLogger(__name__)


class Role(StrEnum):
    CITIZEN = "CITIZEN"
    OFFICER = "OFFICER"
    DEPARTMENT_ADMIN = "DEPARTMENT_ADMIN"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


# Highest privilege first — used to pick the "primary" role for audit records.
ROLE_PRECEDENCE = [Role.PLATFORM_ADMIN, Role.DEPARTMENT_ADMIN, Role.OFFICER, Role.CITIZEN]


@dataclass
class Principal:
    subject: str
    username: str
    roles: set[Role]
    name: str | None = None
    email: str | None = None
    citizen_id: str | None = None
    department_code: str | None = None
    claims: dict = field(default_factory=dict)

    @property
    def primary_role(self) -> Role:
        for role in ROLE_PRECEDENCE:
            if role in self.roles:
                return role
        raise ForbiddenError("No platform role assigned")

    def has_any(self, *roles: Role) -> bool:
        return bool(self.roles.intersection(roles))

    @property
    def is_platform_admin(self) -> bool:
        return Role.PLATFORM_ADMIN in self.roles

    @property
    def is_staff(self) -> bool:
        return self.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN, Role.PLATFORM_ADMIN)


class JWKSCache:
    """Caches the identity provider's signing keys; refreshes on unknown `kid`."""

    def __init__(self, ttl_seconds: int = 600):
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._jwks: PyJWKSet | None = None
        self._fetched_at = 0.0

    def _load(self) -> PyJWKSet:
        settings = get_settings()
        if settings.oidc_static_jwks:
            return PyJWKSet.from_dict(json.loads(settings.oidc_static_jwks))
        resp = httpx.get(settings.oidc_jwks_url, timeout=5.0)
        resp.raise_for_status()
        return PyJWKSet.from_dict(resp.json())

    def get_key(self, kid: str):
        with self._lock:
            stale = time.monotonic() - self._fetched_at > self._ttl
            if self._jwks is None or stale:
                self._refresh()
            key = self._find(kid)
            if key is None:  # key rotation
                self._refresh()
                key = self._find(kid)
            if key is None:
                raise AuthenticationError("Token signed with unknown key")
            return key

    def _refresh(self) -> None:
        try:
            self._jwks = self._load()
            self._fetched_at = time.monotonic()
        except Exception as exc:  # pragma: no cover - network failure path
            logger.error("Unable to fetch JWKS: %s", exc)
            if self._jwks is None:
                raise AuthenticationError("Identity provider unavailable") from exc

    def _find(self, kid: str):
        if self._jwks is None:
            return None
        for k in self._jwks.keys:
            if k.key_id == kid:
                return k
        return None

    def clear(self) -> None:
        with self._lock:
            self._jwks = None
            self._fetched_at = 0.0


jwks_cache = JWKSCache()


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Malformed token") from exc
    if header.get("alg") not in {"RS256", "RS384", "RS512", "PS256"}:
        raise AuthenticationError("Unsupported token algorithm")
    key = jwks_cache.get_key(header.get("kid", ""))
    try:
        return jwt.decode(
            token,
            key=key.key,
            algorithms=[header["alg"]],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
            leeway=10,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token expired", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc}") from exc


def principal_from_claims(claims: dict) -> Principal:
    raw_roles = set(claims.get("realm_access", {}).get("roles", []))
    roles = {Role(r) for r in raw_roles if r in Role.__members__}
    if not roles:
        raise ForbiddenError("Account has no Middly role")
    return Principal(
        subject=claims["sub"],
        username=claims.get("preferred_username") or claims["sub"],
        roles=roles,
        name=claims.get("name"),
        email=claims.get("email"),
        citizen_id=claims.get("citizen_id"),
        department_code=claims.get("department"),
        claims=claims,
    )
