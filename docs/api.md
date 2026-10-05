# API

Interactive OpenAPI documentation: **http://localhost:8000/docs** (through the gateway; raw spec at `/openapi.json`).

All endpoints are under `/api/v1`, require `Authorization: Bearer <Keycloak access token>` (except
`GET /services`), and return errors as:

```json
{ "error": { "code": "CONSENT_REQUIRED", "message": "…", "details": {…}, "correlation_id": "…" } }
```

Every response carries `X-Request-ID`. Send your own `X-Request-ID` to correlate logs, connector calls, events and audit.

Getting a token for API exploration (DEMO-only public client):

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/middly/protocol/openid-connect/token \
  -d grant_type=password -d client_id=middly-demo-cli -d username=citizen1 -d password=Citizen@123 | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/applications
```

## Endpoints

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/auth/me` | any | Current principal |
| GET | `/services`, `/services/{code}` | public | Service catalogue, form schema, DEMO rules |
| POST | `/applications` | citizen | Submit `{service_code, form_data}`; returns detail incl. `consent_request` |
| GET | `/applications` | any (scoped) | Unified tracking; citizen = own, officer = department, admin = all. Filters `status` (comma list), `service`, `q` |
| GET | `/applications/{id}` | owner / department staff / admin | Detail: timeline, sources, data quality, eligibility, profile (consent-gated), history, permissions |
| POST | `/applications/{id}/consent` | owner | Grant consent (shortcut) |
| POST | `/applications/{id}/process` | owner / staff | Run or resume automated verification |
| POST | `/applications/{id}/retry` | owner / staff | Retry a step waiting for an unavailable system |
| POST | `/applications/{id}/sync` | owner / staff | Pull status from the department system |
| POST | `/applications/{id}/approve` | officer of department | Approve (requires active consent) |
| POST | `/applications/{id}/reject` | officer of department | Reject (`remarks` required) |
| POST | `/applications/{id}/request-clarification` | officer of department | Ask the citizen a question |
| POST | `/applications/{id}/clarification-response` | owner | Answer |
| POST | `/applications/{id}/withdraw` | owner | Withdraw (revokes bound consent) |
| GET | `/applications/{id}/audit-logs` | staff | Audit trail of the application |
| GET | `/applications/{id}/consent-access-logs` | owner / staff | Data accesses under its consent |
| POST | `/grievances` · GET `/grievances/{id}` | citizen / any | Register / track a grievance in the department system |
| POST | `/consents` | citizen | Grant `{application_id, data_categories}` |
| GET | `/consents` | citizen (own) / platform admin | Active + history |
| GET | `/consents/{id}` | owner / platform admin | Including access logs |
| POST | `/consents/{id}/revoke` | owner | Revoke immediately |
| GET | `/citizens/me/profile` · POST `/citizens/me/profile/refresh` | citizen | Golden record with provenance; self-service refresh from all sources |
| GET | `/citizens/{id}/profile` | self / officer with active consent | Consent-checked profile |
| GET | `/connectors` · `/connectors/{id}` | admins | Connector cards (health, circuit, 24h stats) |
| GET | `/connectors/{id}/health` · POST `/connectors/health-check` | admins | Live health checks |
| GET | `/connectors/{id}/calls` | admins | Call log |
| PATCH | `/connectors/{id}` | platform admin | Enable/disable, timeout, retries |
| GET | `/workflows/definitions[/{code}]` · `/workflows` · `/workflows/{id}` | admins (instance: viewers of the app) | Definitions and instances |
| GET | `/audit-logs` · `/audit-logs/actions` · `/audit-logs/verify` | platform admin | Search; hash-chain verification |
| GET | `/events` · `/events/topology` · POST `/events/{id}/replay` | admins / platform admin | Event log, broker topology & queue depth, replay |
| GET/POST | `/notifications`, `/notifications/unread-count`, `/notifications/{id}/read`, `/notifications/read-all` | citizen | In-app notifications |
| GET | `/data-quality/issues` · `/data-quality/summary` · POST `/data-quality/issues/{id}/resolve` | admins | Data-quality findings |
| GET | `/admin/overview` | admins | Dashboard KPIs |
| GET | `/demo/scenarios` · POST `/demo/connectors/{key}/fault` · POST `/demo/reset` · POST `/demo/grievances/{id}/resolve` | platform admin, `DEMO_MODE=true` | Demo controls |

Operational: `GET /health` (DB, Redis, RabbitMQ), `GET /health/live`. `GET /metrics` is internal only (blocked at the gateway, scraped by Prometheus on the Docker network).

## Mock department APIs (internal, DEMO)

| System | Endpoints | Auth |
|---|---|---|
| Identity | `POST /identity/oauth/token`, `GET /identity/citizens/{id}` | client credentials |
| Education | `GET /education/citizens/{id}` | `X-API-Key` |
| Employment | `GET /employment/citizens/{id}` | HTTP Basic |
| Skill Development | `POST /skill/applications`, `GET /skill/applications/{id}`, `POST /skill/applications/{id}/decision` | `X-Dept-Key` |
| Grievance | `POST /grievances/oauth/token`, `POST /grievances`, `GET /grievances/{id}`, `POST /grievances/{id}/status` (department side) | client credentials |

All mocks expose `GET /health`, and (with `X-Admin-Key`) `GET|POST /__demo/fault` and `POST /__demo/reset`.
