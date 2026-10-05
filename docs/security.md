# Security

| Control | Implementation |
|---|---|
| Authentication | Keycloak OIDC. The portal (confidential client) uses authorization code + **PKCE** with `state` and `nonce` checks. No custom password handling anywhere in the platform. |
| Session handling | Access, refresh and ID tokens are encrypted (JWE `dir`/A256GCM, key from `SESSION_SECRET`) in `httpOnly`, `SameSite=Lax` cookies (`Secure` on HTTPS). Browser JavaScript never sees tokens. Refresh happens server-side in the BFF. |
| Token validation | Backend verifies RS256 signature against Keycloak JWKS (cached, refreshed on unknown `kid`), `iss`, `aud=middly-api`, `exp`/`iat`/`sub`; algorithm allow-list. |
| Authorisation | Realm roles → `CITIZEN`, `OFFICER`, `DEPARTMENT_ADMIN`, `PLATFORM_ADMIN`. Route-level `require_roles` plus resource checks: citizens only see their own records; officers only their department; decisions only by officers of the owning department (admins cannot decide); audit/demo controls only for platform admins. The portal `proxy.ts` also blocks portal areas by role (defence in depth). |
| Consent | Every data access calls `consent_service.verify` (active, unexpired, department, category, application-bound); allowed and denied attempts are logged. Officer views of personal data and approvals require active consent. Revocation takes effect immediately. |
| Least data | Mobile numbers are masked before storage; demo identity references (`aadhaarRef`) are dropped by the connector; workflow monitoring views redact canonical payloads; admins cannot view personal profiles. |
| Input validation | Pydantic request models with `extra="forbid"`, size limits and patterns; service forms validated server-side against the declarative schema; connector output re-validated against the canonical schema. |
| Rate limiting | Gateway: 30 r/s per IP (burst 60). Backend: per-token/IP fixed window in Redis (`RATE_LIMIT_PER_MINUTE`). |
| Transport/headers | Gateway & app set `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP (frontend + API), `Cache-Control: no-store` on API. `/metrics` not exposed through the gateway. |
| CORS | Allow-list from `CORS_ORIGINS` (the portal origin only). The portal itself calls the API server-side (same-origin BFF). |
| Secrets | Only via environment (`.env`, git-ignored). `scripts/init-env.sh` generates random secrets. Department credentials are referenced by env-var name in connector code and never stored in the DB. Keycloak imports secrets/passwords from env placeholders. |
| Audit | Every consent, data access, fetch failure, forwarding, view, decision, notification, admin action is audited with actor, role, IP, correlation id, source/destination system. Rows are hash-chained (SHA-256) and a DB trigger forbids UPDATE/DELETE; `GET /audit-logs/verify` checks integrity. |
| Correlation | `X-Request-ID` generated/propagated by the gateway → API → connector calls (`X-Correlation-ID`) → events → audit → logs. |
| Containers | Non-root users in backend, frontend and mock images; internal-only services are not published to the host. |

## Demo-only relaxations (must change for production)

- `sslRequired: none` in the Keycloak realm and HTTP everywhere — use TLS termination at the gateway and `KC_HOSTNAME` with https.
- `middly-demo-cli` public client with direct-access grants (for Swagger/curl exploration) — delete it.
- Demo passwords documented in README — use real identity onboarding.
- `DEMO_MODE=true` enables fault injection and reset endpoints — set `DEMO_MODE=false`.
- Keycloak `start-dev` — use `start` with a production configuration.
