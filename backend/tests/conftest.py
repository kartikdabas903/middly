"""Test configuration.

Unit tests need nothing external. Integration tests (marked `integration`) need
Postgres, Redis and the mock department systems — run them inside the stack:

    docker compose exec backend pytest            # all tests
    pytest -m "not integration"                   # unit tests only, anywhere
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]

# ---- Signing key for test tokens (replaces Keycloak's JWKS) ---------------------------------
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-key"


def _jwks() -> str:
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(_KEY.public_key()))
    jwk.update({"kid": _KID, "alg": "RS256", "use": "sig"})
    return json.dumps({"keys": [jwk]})


# Configure the app *before* it is imported anywhere.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
if os.environ.get("REDIS_URL"):
    os.environ["REDIS_URL"] = os.environ["REDIS_URL"].rsplit("/", 1)[0] + "/1"  # isolated Redis DB
os.environ.setdefault("CONNECTORS_PATH", str(ROOT / "connectors"))
os.environ.setdefault("WORKFLOW_CONFIG_PATH", str(ROOT / "workflow-engine"))
if not Path(os.environ["CONNECTORS_PATH"]).exists():
    os.environ["CONNECTORS_PATH"] = "/opt/middly/connectors"
    os.environ["WORKFLOW_CONFIG_PATH"] = "/opt/middly/workflow-engine"
os.environ["EVENT_DISPATCH_MODE"] = "inline"
os.environ["OIDC_STATIC_JWKS"] = _jwks()
os.environ["OIDC_ISSUER"] = "http://test-issuer/realms/middly"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"

USERS = {
    "citizen1": {"sub": "6f1c2a10-0000-4000-8000-000000100001", "roles": ["CITIZEN"], "citizen_id": "100001", "name": "Rahul Sharma"},
    "citizen2": {"sub": "6f1c2a10-0000-4000-8000-000000100002", "roles": ["CITIZEN"], "citizen_id": "100002", "name": "Priya Deshmukh"},
    "citizen3": {"sub": "6f1c2a10-0000-4000-8000-000000100003", "roles": ["CITIZEN"], "citizen_id": "100003", "name": "Amit Verma"},
    "officer1": {"sub": "6f1c2a10-0000-4000-8000-0000000a0001", "roles": ["OFFICER"], "department": "SKILL_DEV", "name": "Anjali Kulkarni"},
    "officer2": {"sub": "6f1c2a10-0000-4000-8000-0000000a0002", "roles": ["OFFICER"], "department": "GRIEVANCE_CELL", "name": "Vikram Joshi"},
    "admin1": {"sub": "6f1c2a10-0000-4000-8000-0000000c0001", "roles": ["PLATFORM_ADMIN"], "name": "Platform Administrator"},
}


def make_token(username: str, **overrides) -> str:
    import jwt

    u = USERS[username]
    now = int(time.time())
    claims = {
        "iss": os.environ["OIDC_ISSUER"],
        "aud": "middly-api",
        "sub": u["sub"],
        "iat": now,
        "exp": now + 600,
        "preferred_username": username,
        "name": u["name"],
        "realm_access": {"roles": u["roles"]},
    }
    if u.get("citizen_id"):
        claims["citizen_id"] = u["citizen_id"]
    if u.get("department"):
        claims["department"] = u["department"]
    claims.update(overrides)
    return jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": _KID})


@pytest.fixture
def token():
    return make_token


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ---- Integration fixtures --------------------------------------------------------------------

@pytest.fixture(scope="session")
def database():
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL not set (run inside docker compose)")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.db.session import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")
    try:
        from app.core.redis import get_redis

        get_redis().flushdb()
    except Exception:
        pass
    from app.core.context import system_context
    from app.db.session import get_sessionmaker
    from app.seed.reference import seed_reference_data

    with system_context(actor="SYSTEM:test-setup"), get_sessionmaker()() as db:
        seed_reference_data(db)
    yield


@pytest.fixture(scope="session")
def client(database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(token):
    def _headers(username: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token(username)}", "X-Request-ID": f"test-{uuid.uuid4()}"}

    return _headers
