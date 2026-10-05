# Database

PostgreSQL 16, managed with SQLAlchemy 2 models (`backend/app/models`) and Alembic
(`backend/alembic/versions/0001_initial_schema.py`). Migrations run automatically when the backend starts.
Keycloak uses a separate database (`keycloak`) on the same server; tests use `middly_test`.

## Tables

| Table | Purpose | Notes |
|---|---|---|
| `users`, `roles`, `user_roles` | Local mirror of Keycloak accounts (JIT provisioned) | `users.id` = token `sub` |
| `citizens` | Canonical golden record | Masked mobile; no identity references; `field_provenance`, `source_status`, `quality_status`; index on (name, dob) for duplicate detection |
| `departments`, `services` | Catalogue; service holds form schema, consent purpose/validity, eligibility rules, workflow code, department connector | |
| `applications` | Application with status, current step, form, profile snapshot, eligibility, data-quality report, decision | Unique `application_number` (`APP-YYYY-NNNN`); indexes on citizen, status, (department, status) |
| `application_sequences` | Per-year counters for application numbers | Row-locked |
| `application_status_history` | Every status change with actor, role, note | |
| `consents` | consent_id, citizen, requesting department, categories, purpose, timestamps, expiry, status, revoked_at | Bound to application; index (citizen, status) |
| `consent_access_logs` | Every data access attempt (ALLOWED/DENIED) with consent, connector, purpose, correlation id | |
| `connectors` | Registry rows synced from plugins (+ admin-tunable enabled/timeout/retries) | Credentials are never stored — only env var names in code |
| `connector_health` | Health check history (status, latency, circuit state) | |
| `connector_calls` | Every connector invocation (operation, status, HTTP code, latency, attempts, correlation id) | |
| `workflow_definitions` | Versioned JSON definitions | Unique (code, version) |
| `workflow_instances` | One per application; status, current step, last error, auto-retry count | |
| `workflow_steps` | One row per step with status, attempts, timestamps, output | Unique (instance, step_key) |
| `events` | Outbox + delivery tracking (status, attempts, processed_by, errors) | Indexes on type, status, aggregate, correlation |
| `notifications` | In-app notifications | Unique `event_id` (idempotent consumers) |
| `audit_logs` | Append-only audit trail with `prev_hash`/`hash` | Trigger `trg_audit_logs_append_only` rejects UPDATE/DELETE |
| `data_quality_issues` | Findings per citizen/application/source with severity and status | |

## ER overview

```
departments 1─* services 1─* applications *─1 citizens 1─* consents
                              │ 1                       │
                              ├─1 workflow_instances 1─* workflow_steps
                              ├─* application_status_history
                              ├─* notifications, data_quality_issues, connector_calls
                              └─1 consents (bound consent)   consents 1─* consent_access_logs
connectors 1─* connector_health, connector_calls      workflow_definitions 1─* workflow_instances
```

## Reset

`./scripts/reset-demo.sh` truncates all platform tables (schema kept), resets mock systems, Redis keys
and RabbitMQ queues. `TRUNCATE` is an explicit maintenance operation; the application itself can only append
to `audit_logs`.
