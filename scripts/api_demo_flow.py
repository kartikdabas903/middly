#!/usr/bin/env python3
"""Headless end-to-end demo through the API gateway (no browser needed).

Runs Scenario 1 (successful cross-department application) and optionally
Scenario 2 (eligibility failure) and Scenario 3 (department outage + retry)
using real Keycloak tokens (DEMO-only `middly-demo-cli` client).

    python scripts/api_demo_flow.py              # scenario 1
    python scripts/api_demo_flow.py --all        # scenarios 1, 2 and 3

Requires only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8000")
KEYCLOAK = os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "middly")
PASSWORDS = {
    "citizen": os.environ.get("DEMO_CITIZEN_PASSWORD", "Citizen@123"),
    "officer": os.environ.get("DEMO_OFFICER_PASSWORD", "Officer@123"),
    "admin": os.environ.get("DEMO_ADMIN_PASSWORD", "Admin@123"),
}
CATEGORIES = ["IDENTITY", "EDUCATION", "EMPLOYMENT"]


def token(username: str) -> str:
    kind = "citizen" if username.startswith("citizen") else "officer" if username.startswith("officer") else "admin"
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": "middly-demo-cli", "username": username, "password": PASSWORDS[kind]}).encode()
    with urllib.request.urlopen(f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token", data=data, timeout=10) as r:
        return json.load(r)["access_token"]


def call(method: str, path: str, tok: str, body: dict | None = None, expect_error: bool = False) -> dict:
    req = urllib.request.Request(GATEWAY + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        payload = json.loads(e.read() or b"{}")
        if expect_error:
            return {"_status": e.code, **payload}
        print(f"  ✗ {method} {path} -> HTTP {e.code}: {payload}")
        raise SystemExit(1)


def step(msg: str) -> None:
    print(f"\n▶ {msg}")


def timeline(app: dict) -> None:
    icons = {"done": "✓", "current": "●", "blocked": "⚠", "skipped": "–", "pending": "○", "failed": "✗"}
    for s in app["timeline"]:
        print(f"    {icons.get(s['state'], '?')} {s['label']:<26} {s['status']}")


def apply(citizen: str, form: dict) -> tuple[str, dict]:
    tok = token(citizen)
    app = call("POST", "/api/v1/applications", tok, {"service_code": "SKILL_DEV_SCHEME", "form_data": form})
    print(f"  application {app['application_number']} status={app['status']} (consent requested: {app['consent_request']['categories']})")
    app = call("POST", "/api/v1/consents", tok, {"application_id": app["id"], "data_categories": CATEGORIES}) and app
    print("  consent granted for", ", ".join(CATEGORIES))
    app = call("POST", f"/api/v1/applications/{app['id']}/process", tok)
    print(f"  after processing: status={app['status']} eligible={app['eligible']} data_quality={app['data_quality']}")
    timeline(app)
    return tok, app


def scenario_1() -> None:
    step("Scenario 1 — citizen1 applies for the Skill Development Training Scheme")
    tok, app = apply("citizen1", {"preferred_trade": "SOFTWARE_DEVELOPMENT", "preferred_district": "Pune", "training_mode": "HYBRID"})
    assert app["status"] == "UNDER_REVIEW", app["status"]
    for src in app["sources"]:
        print(f"    source {src['system']:<22} {src['state']}")
    print("  provenance:", {k: v["source"] for k, v in app["profile"]["provenance"].items()})

    step("officer1 reviews and approves")
    otok = token("officer1")
    queue = call("GET", "/api/v1/applications?status=UNDER_REVIEW", otok)
    print(f"  officer queue: {[a['application_number'] for a in queue['items']]}")
    detail = call("GET", f"/api/v1/applications/{app['id']}", otok)
    print(f"  officer sees consolidated profile: {detail['profile']['full_name']}, {detail['profile']['district']}, "
          f"{detail['profile']['education']['highest_qualification']}, {detail['profile']['employment_status']}")
    approved = call("POST", f"/api/v1/applications/{app['id']}/approve", otok, {"remarks": "Verified via registries. Approved."})
    print(f"  status={approved['status']} workflow={approved['workflow_status']}")

    step("RabbitMQ → notification consumer → citizen notification")
    for _ in range(30):
        notes = call("GET", "/api/v1/notifications", tok)
        hit = next((n for n in notes["items"] if app["application_number"] in n["message"] and n["title"] == "Application approved"), None)
        if hit:
            print(f"  🔔 {hit['message']}")
            break
        time.sleep(1)
    else:
        raise SystemExit("  ✗ approval notification not received")
    final = call("GET", f"/api/v1/applications/{app['id']}", tok)
    timeline(final)
    assert final["workflow_status"] == "COMPLETED", final["workflow_status"]


def scenario_2() -> None:
    step("Scenario 2 — citizen3 (outside Maharashtra, age 41, employed) applies")
    _, app = apply("citizen3", {"preferred_trade": "DATA_ENTRY", "preferred_district": "Nagpur", "training_mode": "ONLINE"})
    print(f"  failed rules: {app['eligibility']['failed_rules']}")
    assert app["status"] == "REJECTED"


def scenario_3() -> None:
    step("Scenario 3 — Employment Registry outage")
    atok = token("admin1")
    call("POST", "/api/v1/demo/connectors/employment/fault", atok, {"mode": "DOWN"})
    print("  admin set Employment Registry to DOWN")
    try:
        tok, app = apply("citizen2", {"preferred_trade": "ELECTRONICS_REPAIR", "preferred_district": "Nagpur", "training_mode": "CLASSROOM"})
        assert app["status"] == "WAITING_FOR_SOURCE", app["status"]
        blocked = next(s for s in app["sources"] if s["state"] == "UNAVAILABLE")
        print(f"  {blocked['system']} ● Temporarily unavailable — {blocked['error']}")
    finally:
        call("POST", "/api/v1/demo/connectors/employment/fault", atok, {"mode": "HEALTHY"})
        print("  admin restored Employment Registry")
    app = call("POST", f"/api/v1/applications/{app['id']}/retry", tok)
    print(f"  after retry: status={app['status']}")
    timeline(app)
    assert app["status"] == "UNDER_REVIEW"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="run scenarios 1, 2 and 3")
    args = parser.parse_args()
    scenario_1()
    if args.all:
        scenario_2()
        scenario_3()
    step("Admin dashboard")
    ov = call("GET", "/api/v1/admin/overview", token("admin1"))
    print(f"  API requests={ov['api']['requests']} connector calls={ov['connector_calls']['total']} "
          f"events={sum(ov['events']['by_status'].values())} avg processing={ov['avg_processing_seconds']}s")
    print("\n✅ Demo flow completed")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
