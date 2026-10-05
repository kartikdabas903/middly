# Architecture

## Principles

1. **Connect, don't replace.** Department systems keep their data and logic. The platform reads through
   connectors and writes back only through department APIs (e.g. decisions), never by editing source records.
2. **The core knows interfaces, not departments.** Workflows reference connectors by key and data by category;
   department specifics live in plugins.
3. **Consent before data.** Every read of citizen data is gated by an active, purpose-bound consent and logged.
4. **Failure is a state, not a crash.** Outages become persisted waiting states with retry.
5. **Everything is attributable.** Correlation IDs flow from the gateway through API, connectors, events and audit.

## Components

| Component | Responsibility | Code |
|---|---|---|
| Portals + BFF | Citizen, officer, admin UIs. OIDC authorization code + PKCE; tokens stored encrypted (A256GCM) in httpOnly cookies; `/bff/*` proxies API calls with the bearer token, refreshing it when needed | `frontend/src/app`, `frontend/src/lib/server` |
| API gateway | Single entry point: routing, `X-Request-ID` generation/propagation, per-IP rate limiting, coarse bearer-token check, security headers, JSON access logs, uniform JSON errors | `infrastructure/gateway/nginx.conf` |
| Identity | Keycloak realm `middly` with realm roles, `citizen_id`/`department` claims, API audience | `infrastructure/keycloak/realm-middly.json` |
| Platform API | FastAPI routers → services → repositories/models | `backend/app/api`, `services`, `repositories` |
| Connector SDK | `BaseConnector`, resilient HTTP (timeout, retry+exponential backoff+jitter), Redis circuit breaker, auth helpers, normalisation helpers, plugin registry | `backend/app/integration` |
| MDM | Canonical schema & validation, survivorship merge with provenance, data-quality rules | `backend/app/mdm` |
| Workflow engine | Executes JSON definitions with typed step handlers; persists instance and step state | `backend/app/workflow`, `workflow-engine/` |
| Eligibility | Declarative rules (equals / in / age_between / min_level / …) | `backend/app/eligibility` |
| Events | Transactional outbox, RabbitMQ publisher, consumers, DLQ | `backend/app/events` |
| Worker | Consumers + outbox relay + health monitor + auto-retry + external status sync; exposes metrics | `backend/app/worker.py` |
| Audit | Separate-transaction, advisory-locked, SHA-256 hash chain; DB trigger blocks UPDATE/DELETE | `backend/app/services/audit_service.py` |
| Mock departments | Five independent FastAPI apps with different auth and formats, fault injection | `connectors/*/mock_service` |
| Observability | Prometheus metrics (API, connectors, workflow, applications, events), Grafana dashboard, alerts | `backend/app/core/metrics.py`, `monitoring/` |

## Request path (officer approves)

```
Browser ─POST /bff/applications/{id}/approve─► Next.js BFF (decrypt session, refresh token if needed)
  ─► Nginx gateway (X-Request-ID, rate limit) ─► FastAPI
       middleware: correlation id, rate limit (per token), metrics, security headers
       deps: JWT validation (JWKS), principal, JIT user provisioning, RBAC (OFFICER of same department)
       service: consent still active? → WorkflowEngine.officer_decision
         → human_review COMPLETED, decision COMPLETED, application APPROVED
         → outbox row APPLICATION_APPROVED (same transaction) → audit OFFICER_APPROVED_APPLICATION
       commit ─► after-commit hook publishes to RabbitMQ (middly.events, key application.approved)
  worker:
       notification-dispatcher → emits NOTIFICATION_REQUESTED
       notification-service    → stores notification (idempotent by source event id)
                               → completes NOTIFICATION_SENT step → workflow COMPLETED
       department-sync         → SkillDevelopmentConnector.update_application (retry ×3 → DLQ)
```

## Resilience

| Mechanism | Where |
|---|---|
| Timeouts (connect ≤2 s, total 3 s default, per connector) | `BaseConnector.request` |
| Retries with exponential backoff + jitter (retryable errors only: 5xx, 429, timeouts, transport) | `BaseConnector.request` |
| Circuit breaker shared across API and worker (Redis): 3 failures → OPEN 30 s → HALF_OPEN trial | `integration/circuit_breaker.py` |
| Persisted waiting state `WAITING_FOR_SOURCE`, completed steps are never re-run | `workflow/engine.py` |
| Manual retry (`POST /applications/{id}/retry`) and bounded automatic retry | API, `worker.job_auto_retry` |
| Transactional outbox + relay for broker outages | `events/outbox.py` |
| Consumer retry (×3 with backoff) then dead-letter queue `middly.dead-letter` | `worker._on_message` |
| Idempotent consumers (processed_by per event, unique notification per source event) | `events/handlers.py` |
| Health checks every 30 s, results in `connector_health` and `middly_connector_up` | worker, `connector_service` |

## Deployment view

Docker Compose network `middly-net` with: frontend, gateway, backend, worker, postgres, redis, rabbitmq,
keycloak, prometheus, grafana and five mock department systems. Only the portal, gateway, Keycloak and the
observability UIs are published to the host; the backend, database and mocks are internal.
