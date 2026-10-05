"""Shared scaffolding for DEMO / MOCK department systems.

These services imitate independent legacy department systems for the hackathon
demo. They are NOT real government systems and contain only fictitious data.

Features:
  * fault injection (HEALTHY / DEGRADED / SLOW / DOWN / FLAKY) for resilience demos
  * demo reset hook
  * three different authentication schemes (API key, HTTP Basic, OAuth2 client credentials)
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

FAULT_MODES = {"HEALTHY", "DEGRADED", "SLOW", "DOWN", "FLAKY"}


class FaultState:
    def __init__(self) -> None:
        self.mode = "HEALTHY"
        self.updated_at = time.time()

    def as_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "updated_at": self.updated_at}


class FaultRequest(BaseModel):
    mode: str


def _admin_guard(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MOCK_ADMIN_KEY", "")
    if not expected or not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key")


def create_mock_app(*, code: str, title: str, description: str, reset_hook: Callable[[], None] | None = None) -> FastAPI:
    app = FastAPI(
        title=f"{title} (DEMO / MOCK SYSTEM)",
        description=f"**DEMO MOCK — not an official government system.** {description}",
        version="1.0.0-demo",
    )
    fault = FaultState()
    app.state.fault = fault
    log = logging.getLogger(code)

    @app.middleware("http")
    async def fault_injection(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/__demo") and path not in ("/docs", "/openapi.json"):
            mode = fault.mode
            if mode == "DOWN":
                return JSONResponse(status_code=503, content={"status": "DOWN", "message": f"{title} is temporarily unavailable"})
            if mode == "FLAKY" and random.random() < 0.5:
                return JSONResponse(status_code=502, content={"status": "ERROR", "message": "Upstream gateway error"})
            if mode == "SLOW":
                await asyncio.sleep(6.0)
            elif mode == "DEGRADED":
                await asyncio.sleep(1.8)
        response = await call_next(request)
        response.headers["X-Demo-System"] = "true"
        log.info("%s %s -> %s corr=%s", request.method, path, response.status_code, request.headers.get("x-correlation-id"))
        return response

    @app.get("/health", tags=["ops"])
    def health():
        status = {"HEALTHY": "UP", "DEGRADED": "DEGRADED", "SLOW": "DEGRADED", "FLAKY": "DEGRADED"}.get(fault.mode, "DOWN")
        return {"status": status, "system": title, "demo": True, "fault_mode": fault.mode}

    @app.get("/__demo/fault", tags=["demo"], dependencies=[Depends(_admin_guard)])
    def get_fault():
        return fault.as_dict()

    @app.post("/__demo/fault", tags=["demo"], dependencies=[Depends(_admin_guard)])
    def set_fault(req: FaultRequest):
        mode = req.mode.upper()
        if mode not in FAULT_MODES:
            raise HTTPException(status_code=422, detail=f"mode must be one of {sorted(FAULT_MODES)}")
        fault.mode = mode
        fault.updated_at = time.time()
        log.warning("Fault mode set to %s", mode)
        return fault.as_dict()

    @app.post("/__demo/reset", tags=["demo"], dependencies=[Depends(_admin_guard)])
    def reset():
        fault.mode = "HEALTHY"
        if reset_hook:
            reset_hook()
        return {"reset": True}

    return app


# --------------------------------------------------------------------------- auth schemes

def api_key_auth(env_var: str, header: str = "X-API-Key"):
    def guard(request: Request) -> None:
        provided = request.headers.get(header)
        expected = os.environ.get(env_var, "")
        if not expected or not provided or not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return guard


def basic_auth(user_env: str, password_env: str):
    def guard(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.lower().startswith("basic "):
            raise HTTPException(status_code=401, detail="Basic authentication required", headers={"WWW-Authenticate": "Basic"})
        try:
            user, _, password = base64.b64decode(authorization[6:]).decode().partition(":")
        except Exception:
            raise HTTPException(status_code=401, detail="Malformed credentials")
        ok_user = secrets.compare_digest(user, os.environ.get(user_env, ""))
        ok_pass = secrets.compare_digest(password, os.environ.get(password_env, ""))
        if not (ok_user and ok_pass and os.environ.get(password_env)):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    return guard


class OAuthClientCredentials:
    """Minimal OAuth2 client-credentials token endpoint for a mock department."""

    def __init__(self, client_id_env: str, client_secret_env: str, ttl_seconds: int = 300):
        self.client_id_env = client_id_env
        self.client_secret_env = client_secret_env
        self.ttl = ttl_seconds
        self._tokens: dict[str, float] = {}
        self._lock = threading.Lock()

    def mount(self, app: FastAPI, path: str) -> None:
        @app.post(path, tags=["auth"])
        def token(grant_type: str = Form(...), client_id: str = Form(...), client_secret: str = Form(...)):
            if grant_type != "client_credentials":
                raise HTTPException(status_code=400, detail="unsupported_grant_type")
            ok = secrets.compare_digest(client_id, os.environ.get(self.client_id_env, "")) and secrets.compare_digest(
                client_secret, os.environ.get(self.client_secret_env, "")
            )
            if not ok or not os.environ.get(self.client_secret_env):
                raise HTTPException(status_code=401, detail="invalid_client")
            tok = secrets.token_urlsafe(32)
            with self._lock:
                self._tokens[tok] = time.time() + self.ttl
            return {"access_token": tok, "token_type": "Bearer", "expires_in": self.ttl}

    def guard(self, authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required")
        tok = authorization[7:]
        with self._lock:
            exp = self._tokens.get(tok)
        if not exp or exp < time.time():
            raise HTTPException(status_code=401, detail="Token invalid or expired")


# --------------------------------------------------------------------------- storage

def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


class DocumentStore:
    """Tiny SQLite-backed JSON document store for mock systems that accept writes."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("CREATE TABLE IF NOT EXISTS docs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            self._conn.execute("CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            self._conn.commit()

    def next_value(self, name: str) -> int:
        with self._lock:
            row = self._conn.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
            value = (row[0] if row else 0) + 1
            self._conn.execute("INSERT OR REPLACE INTO counters(name, value) VALUES (?, ?)", (name, value))
            self._conn.commit()
            return value

    def put(self, doc_id: str, body: dict) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO docs(id, body) VALUES (?, ?)", (doc_id, json.dumps(body)))
            self._conn.commit()

    def get(self, doc_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT body FROM docs WHERE id=?", (doc_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT body FROM docs").fetchall()
        return [json.loads(r[0]) for r in rows]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM docs")
            self._conn.execute("DELETE FROM counters")
            self._conn.commit()
