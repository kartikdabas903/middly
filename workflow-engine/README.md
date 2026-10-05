# Workflow engine configuration

Configuration consumed by the generic workflow engine (`backend/app/workflow/`).
Loaded into the database by the seeder (`workflow_definitions`, `services.eligibility_rules`).

```
definitions/*.json   versioned workflow definitions (steps + step types)
rules/*.json         eligibility rule sets — DEMO rules, not official criteria
services.json        departments and services (form schema, consent purpose, workflow, rules)
```

## Step types

| type | behaviour | waits as |
|---|---|---|
| `start` | emits APPLICATION_CREATED (or the event named in `event`) | — |
| `consent` | requires an active consent bound to the application for `categories` | WAITING_FOR_CONSENT |
| `fetch` | consent-checked call to `connector` for `category`, canonical validation | WAITING_FOR_SOURCE on outage |
| `validation` | merge fragments → golden record, data-quality checks | — |
| `eligibility` | evaluates the service rule set; `on_ineligible: AUTO_REJECT` ends the workflow | — |
| `department_submit` | registers the application in the department system | WAITING_FOR_SOURCE on outage |
| `human_review` | officer approve / reject / request clarification | WAITING_FOR_OFFICER / WAITING_FOR_CITIZEN |
| `decision` | records the final decision, emits APPLICATION_APPROVED/REJECTED | — |
| `notification` | completed by the notification consumer after the event is processed | WAITING_FOR_EVENT |
| `external_status` | polls the department system until `complete_on` / `reject_on` | WAITING_FOR_EXTERNAL |

New step types are added by implementing a handler in `backend/app/workflow/handlers.py`.
