# Demo guide (SIH presentation)

**Before the demo**

```bash
./scripts/start.sh                                   # if not running
./scripts/reset-demo.sh && ./scripts/seed-demo.sh    # predictable data; live demo starts at APP-2026-0001
```

Open four tabs: portal `http://localhost:3000`, Grafana `:3001`, RabbitMQ `:15672`, Swagger `:8000/docs`.
Use a private window per persona (or sign out between personas) — sessions are cookie-based.

Seeded history (2025) gives context: APP-2025-0001 (withdrawn, consent revoked), 0002 (outage → retry →
approved), 0003 (duplicate record, ineligible), 0004 (grievance resolved by department), 0005 (grievance in progress).

---

## Scenario 1 — Successful cross-department application (≈5 min)

| Step | Action | Talking point |
|---|---|---|
| 1 | Sign in as **citizen1** (Keycloak page) | OIDC + PKCE; tokens stay server-side |
| 2 | *Apply for a service* → **Skill Development Training Scheme** | Only 3 scheme-specific choices — no documents |
| 3 | Choose trade / district / mode → **Continue** | Application `APP-2026-0001` created; workflow started |
| 4 | Consent card: Identity / Education / Employment **Allowed** → **Allow & continue** | Purpose, department, 180-day validity, revocable |
| 5 | Verification animation | Three departments, three auth schemes, three formats |
| 6 | Application page | Timeline ✓…● Officer review; sources VERIFIED; DEMO eligibility; data quality |
| 7 | *My data* tab | Canonical profile with **provenance chips** per field |
| 8 | Sign in as **officer1** → Applications → APP-2026-0001 | Consolidated profile, verification, workflow, audit tabs — read-only source data |
| 9 | **Approve** | Decision → outbox → RabbitMQ |
| 10 | (Optional) RabbitMQ UI → queues | `notification-dispatcher`, `notification-service`, `department-sync`, `event-log` |
| 11 | Sign in as **citizen1** → bell | **"Application APP-2026-0001 approved."**; timeline fully green; department reference + batch |
| 12 | Sign in as **admin1** → dashboard | API requests, connector calls, workflow states, events, audit, avg processing time |
| 13 | Audit logs → **Verify integrity**; click a correlation id | Tamper-evident chain; one request traced across systems |

## Scenario 2 — Eligibility failure (≈2 min)

citizen3 (Amit Verma) applies → consent → result: **Rejected automatically**. Show the eligibility card
(MAHARASHTRA_RESIDENT ✗, AGE_RANGE ✗, EDUCATION ✓, EMPLOYMENT ✗) and data quality **CONFLICT**
(Verma vs Varma, DOB mismatch). Emphasise: rules are configurable JSON and clearly marked DEMO.

## Scenario 3 — Department API failure and retry (≈3 min)

1. admin1 → dashboard → *Demo scenarios* → Employment Registry **Down** (card turns red; Grafana connector panel shows DOWN).
2. citizen2 applies and consents → Identity ✓, Education ✓, **Employment Registry ● Temporarily unavailable**;
   workflow `WAITING_FOR_SOURCE`; citizen gets a "Verification delayed" notification. Nothing crashes.
3. (Optional) Retry while still down 2–3 times → circuit breaker **OPEN** on the connector card (fast-fail).
4. admin1 sets Employment Registry **Healthy**.
5. citizen2 → **Retry now** (or wait for the worker's automatic retry) → processing resumes from the failed step → Officer review.

## Extra talking points

- **Add a department without touching the core:** show `connectors/README.md` / Connectors page snippet.
- **Consent revocation:** citizen2 → Consents → Revoke → officer view now hides data and approval is blocked.
- **Grievance tracking:** citizen1 raises a grievance; it lives in the Grievance system and is tracked in the same dashboard. Admin can simulate the department resolving it (`POST /api/v1/demo/grievances/{id}/resolve`).
- **Headless run:** `python scripts/api_demo_flow.py --all` executes all three scenarios via the API in ~20 s.

## Recovery during the demo

- Anything odd → admin dashboard **Reset demo data** (≈10 s) or `./scripts/reset-demo.sh && ./scripts/seed-demo.sh`.
- A fault left on → *Demo scenarios* → set every system to **Healthy**.
