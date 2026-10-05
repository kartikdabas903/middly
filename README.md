# Middly

**The interoperability layer for public services.** Middly connects the systems departments already run so
citizens apply once, consent to how their data is shared, and track every application in one place.

> This repository ships a **sandbox** environment: the five department systems are sample services with
> fictitious citizens, and the eligibility rules are sample rules. Set `DEMO_MODE=false`
> when connecting real department endpoints.

## 1. Problem

Departments run independent portals, registries and workflow systems with different data formats,
identifiers, authentication mechanisms and APIs. Citizens re-submit the same data to every department,
applications stall between systems, and nobody has a single view of an application.

## 2. Solution

Middly is **interoperability middleware**, not a replacement. It connects existing systems through
standard APIs and reusable connectors, with consent-based data sharing, master data management,
workflow orchestration, events, unified tracking, audit and monitoring.

## 3. Architecture

```
 Browser ──► Next.js portals (citizen / officer / admin) ── BFF: OIDC code+PKCE, encrypted httpOnly session
                 │                                     │
                 │ sign-in                             ▼
             Keycloak (OIDC)              Nginx API gateway  (request IDs, rate limit, auth pre-check, headers)
                                                       ▼
                                     FastAPI platform core
     ┌──────────────┬──────────────┬───────────────┬─────────────┬──────────────┬──────────────┐
     │ Consent      │ Master data  │ Workflow      │ Eligibility │ Audit        │ Admin / KPIs │
     │ (verify on   │ (canonical   │ engine (JSON  │ rules (DEMO)│ (append-only │              │
     │  every read) │  model, DQ)  │  definitions) │             │  hash chain) │              │
     └──────────────┴──────┬───────┴───────┬───────┴─────────────┴──────────────┴──────────────┘
                           │ Connector SDK │ transactional outbox
          (timeouts, retries+backoff,      ▼
           circuit breaker, telemetry)  RabbitMQ ──► worker: notifications · department sync · event log
                           │                         (+ outbox relay, health monitor, auto-retry, status sync)
     ┌─────────────┬───────┴──────┬──────────────┬──────────────┐
  Identity     Education      Employment    Skill Dev.     Grievance        ← DEMO mock department systems
  OAuth2       API key        HTTP Basic    API key        OAuth2             (each with its own format)

 PostgreSQL (platform + Keycloak) · Redis (rate limits, circuit breakers, token cache) · Prometheus + Grafana
```

Details: [docs/architecture.md](docs/architecture.md).

## 4. Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router, TypeScript), Tailwind CSS 4, shadcn/ui (Base UI), TanStack Query, React Hook Form + Zod, Recharts |
| Backend | Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Messaging / cache | RabbitMQ 4 (topic exchange + DLX), Redis 7 |
| Identity | Keycloak 26 (OIDC, JWT, realm roles) |
| Gateway | Nginx (Kong-compatible responsibilities) |
| Observability | Prometheus, Grafana (provisioned dashboard), structured JSON logs with correlation IDs |
| Testing | Pytest (unit + integration), Playwright (E2E demo) |

## 5. How interoperability works

1. A **connector plugin** per department (`connectors/<dept>/connector.py`) implements
   `authenticate · health_check · get_citizen · get_application · transform_response · handle_error`.
2. The **registry** discovers plugins at runtime — the core never imports a department.
3. `transform_response` maps source fields (`fullName`, `student_name`, `candidateName`, …) into the
   **canonical citizen model**; the core **re-validates** every fragment (invalid fields are dropped and reported).
4. **Survivorship rules** merge fragments into a golden record with **field provenance**.
5. **Data-quality checks** flag missing fields, invalid formats, duplicates, name/DOB conflicts, stale data,
   invalid responses and unavailable sources.

See [docs/interoperability.md](docs/interoperability.md) and [connectors/README.md](connectors/README.md).

## 6. Security

Keycloak OIDC · JWT signature/issuer/audience/expiry validation · RBAC (`CITIZEN`, `OFFICER`,
`DEPARTMENT_ADMIN`, `PLATFORM_ADMIN`) · consent verification on every data access · tokens kept server-side
in encrypted httpOnly cookies · gateway + per-token rate limiting · strict input validation · security headers
· CORS allow-list · secrets only via environment · masked mobile numbers, no identity references stored ·
append-only hash-chained audit log. See [docs/security.md](docs/security.md).

## 7. Consent

The citizen sees the requesting department, purpose, validity and each data category (`Identity /
Education / Employment Information — Allowed`) and must explicitly allow them. Consents are bound to the
application and are time-limited and revocable. Every access (allowed or denied) is recorded in
`consent_access_logs`; after revocation officers lose access to the consolidated profile and cannot approve.

## 8. Workflow

`SKILL_DEVELOPMENT_APPLICATION` (JSON in `workflow-engine/definitions`):
Application submitted → Consent → Fetch identity → Fetch education → Fetch employment → Data validation →
Eligibility → Forwarded to department → Officer review → Decision → Notification. All step states are persisted;
outages park the workflow in `WAITING_FOR_SOURCE` with manual and automatic retry.

## 9. Event-driven architecture

Events (`APPLICATION_CREATED`, `CONSENT_GRANTED`, `DATA_FETCHED`, `ELIGIBILITY_COMPLETED`,
`APPLICATION_SUBMITTED`, `APPLICATION_APPROVED`, `APPLICATION_REJECTED`, `GRIEVANCE_CREATED`,
`NOTIFICATION_REQUESTED`, …) are written to a **transactional outbox**, published to RabbitMQ after commit and
consumed by the worker: *notification-dispatcher → notification-service* (stores the notification and completes
the workflow step), *department-sync* (pushes decisions to the department system, retries then dead-letters),
*event-log*. Every event row records its delivery status and consumers.

## 10. Running locally

Prerequisites: Docker (with Compose v2), ~6 GB free RAM, Node 20.9+, Python 3.11+.

Install all development dependencies in one go (`.env`, backend venv + dev deps, frontend deps,
Playwright Chromium, Docker images):

```bash
./scripts/install-dev.sh                                              # macOS / Linux / Git Bash
powershell -ExecutionPolicy Bypass -File scripts\install-dev.ps1      # Windows PowerShell
```

Then start the stack:

```bash
cd middly
./scripts/start.sh            # creates .env with random secrets if missing, builds, starts, waits for health
# or: cp .env.example .env && docker compose up -d --build
```

First start takes a few minutes (image builds, Keycloak import). The backend migrates the database and seeds
the demo automatically. Then open:

| | URL |
|---|---|
| Portal | http://localhost:3000 |
| API docs (Swagger via gateway) | http://localhost:8000/docs |
| Keycloak | http://localhost:8080 (admin: `KEYCLOAK_ADMIN_USER` / `KEYCLOAK_ADMIN_PASSWORD`) |
| Grafana | http://localhost:3001 (`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`) |
| Prometheus | http://localhost:9090 |
| RabbitMQ management | http://localhost:15672 (`RABBITMQ_USER` / `RABBITMQ_PASSWORD`) |

Demo reset (predictable data, the live demo starts at `APP-2026-0001`):

```bash
./scripts/reset-demo.sh && ./scripts/seed-demo.sh     # or "Reset demo data" on the admin dashboard
```

Tests:

```bash
./scripts/test.sh                                      # pytest (unit+integration) + Playwright E2E
docker compose exec backend pytest                     # backend only
cd frontend && npx playwright install chromium && npx playwright test
python scripts/api_demo_flow.py --all                  # headless API walkthrough of all 3 scenarios
```

Development with live code reload of backend/mocks: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`.

## 11. Demo credentials (DEMO only — set in `.env`)

| Username | Password | Role | Persona |
|---|---|---|---|
| citizen1 | Citizen@123 | Citizen | Rahul Sharma, Pune — eligible (Scenario 1) |
| citizen2 | Citizen@123 | Citizen | Priya Deshmukh, Nagpur — outage & retry (Scenario 3) |
| citizen3 | Citizen@123 | Citizen | Amit Verma, Indore — not eligible (Scenario 2) |
| citizen4 | Citizen@123 | Citizen | Sneha Patil, Kolhapur — historical approved application |
| officer1 | Officer@123 | Officer | Skill Development Department (Demo) |
| officer2 | Officer@123 | Officer | Public Grievance Cell (Demo) |
| deptadmin1 | DeptAdmin@123 | Department admin + officer | Skill Development |
| admin1 | Admin@123 | Platform admin | Monitoring + demo controls |

## 12. Demo walkthrough

1. **citizen1** → *Apply for a service* → Skill Development Training Scheme → choose trade, district, mode.
2. Consent screen: Identity / Education / Employment → **Allow & continue**.
3. Watch Identity Service, Education Registry and Employment Registry being contacted; responses normalised,
   quality-checked, DEMO eligibility evaluated → `APP-2026-0001` is **Under officer review** with a live timeline.
4. **officer1** → Applications → `APP-2026-0001` → consolidated profile with field provenance → **Approve**.
5. `APPLICATION_APPROVED` → RabbitMQ → notification consumer → **citizen1** sees
   *"Application APP-2026-0001 approved."* and a fully completed timeline.
6. **admin1** → dashboard: API requests, connector calls, workflow, events, audit log, processing time.
7. Scenario 2: **citizen3** applies → auto-rejected with failed rules and data-quality conflicts.
8. Scenario 3: admin sets *Employment Registry → Down*; **citizen2** applies → *Employment Registry ● Temporarily
   unavailable* / `WAITING_FOR_SOURCE`; restore → **Retry now** → officer review.

Full script with talking points: [docs/demo-guide.md](docs/demo-guide.md).

## Repository layout

```
frontend/         Next.js portals + BFF (OIDC, session, API proxy) + Playwright E2E
backend/          FastAPI core: api/ services/ repositories/ models/ schemas/ integration/ mdm/
                  eligibility/ workflow/ events/ seed/ + Alembic migrations + pytest
connectors/       connector plugins + DEMO mock department systems (identity, education, employment,
                  skill-development, grievance)
workflow-engine/  workflow definitions, DEMO eligibility rules, service catalogue (JSON)
infrastructure/   Nginx gateway, Keycloak realm import, Postgres init
monitoring/       Prometheus config/alerts, Grafana provisioning + dashboard
docs/             architecture, api, database, security, interoperability, demo-guide, deployment
scripts/          start, init-env, reset-demo, seed-demo, test, api_demo_flow.py
```
