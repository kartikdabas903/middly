"""Connector SDK resilience: retries with backoff, error translation, fast-fail when the circuit is open."""
from __future__ import annotations

import httpx
import pytest

import app.integration.circuit_breaker as cbmod
from app.integration.errors import CircuitOpenError, RecordNotFoundError, SourceTimeoutError, SourceUnavailableError
from app.integration.sdk import BaseConnector, ConnectorConfig


class _Fake(BaseConnector):
    key = "fake"
    system_name = "Fake Registry"

    def authenticate(self):
        return {}


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    def boom():
        raise ConnectionError("no redis")

    monkeypatch.setattr(cbmod, "get_redis", boom)


def make(handler, retries=2):
    conn = _Fake(ConnectorConfig(key=f"fake-{id(handler)}", base_url="http://fake", max_retries=retries, backoff_base_seconds=0.001, circuit_failure_threshold=2))
    conn._client = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    return conn


def test_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"ok": True})

    conn = make(handler)
    assert conn.get_json("/x") == {"ok": True}
    assert conn.last_call.attempts == 3


def test_not_found_is_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    with pytest.raises(RecordNotFoundError):
        make(handler).get_json("/x")
    assert calls["n"] == 1


def test_timeout_translated_and_circuit_opens():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    conn = make(handler, retries=0)
    with pytest.raises(SourceTimeoutError):
        conn.get_json("/x")
    with pytest.raises(SourceUnavailableError):
        conn.get_json("/x")
    with pytest.raises(CircuitOpenError):  # threshold reached -> fail fast without calling the source
        conn.get_json("/x")


def test_correlation_id_propagated():
    seen = {}

    def handler(request):
        seen["corr"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={})

    conn = make(handler)
    conn.config.correlation_id = "corr-123"
    conn.get_json("/x")
    assert seen["corr"] == "corr-123"
