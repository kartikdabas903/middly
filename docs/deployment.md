# Deployment

## Local / demo (Docker Compose)

```bash
./scripts/init-env.sh        # .env with random secrets (or: cp .env.example .env)
docker compose up -d --build
docker compose ps            # all services should be "healthy"
```

Startup order is enforced with health checks: postgres/redis/rabbitmq/mocks → backend (runs `alembic upgrade head`,
then seeds if the database is empty) → worker, gateway → frontend (also waits for Keycloak).

| Service | Image / build | Host port | Health check |
|---|---|---|---|
| frontend | `frontend/Dockerfile` (Next.js standalone) | 3000 | `GET /api/health` |
| gateway | nginx:1.29-alpine | 8000 | `GET /gateway/health` |
| backend | `backend/Dockerfile` | — (internal) | `GET /health/live` |
| worker | backend image, `worker` command | — | metrics endpoint :9100 |
| postgres | postgres:16-alpine | — | `pg_isready` |
| redis | redis:7-alpine | — | `PING` |
| rabbitmq | rabbitmq:4.1-management-alpine | 15672 | `rabbitmq-diagnostics ping` |
| keycloak | quay.io/keycloak/keycloak:26.4 | 8080 | `/health/ready` (mgmt port) |
| prometheus | prom/prometheus | 9090 | `/-/ready` |
| grafana | grafana/grafana | 3001 | `/api/health` |
| mock-identity / -education / -employment / -skill / -grievance | `connectors/Dockerfile.mock` | — | `GET /docs` |

Useful commands:

```bash
docker compose logs -f backend worker            # structured JSON logs with correlation_id
docker compose exec backend alembic upgrade head # migrations (automatic on start)
docker compose exec backend python -m app.seed.run seed-if-empty | seed | reset | reset-and-seed
docker compose down -v                           # remove everything including volumes
```

Changing ports or the public Keycloak URL: edit `.env` (`KEYCLOAK_PUBLIC_URL` must match the host port, because it
is the token issuer). Changing `OIDC_CLIENT_SECRET` or demo passwords after the realm was imported requires
`docker compose down -v` (or updating them in the Keycloak admin console).

## Towards production

- **TLS** at the edge; set `FRONTEND_URL`/`KEYCLOAK_PUBLIC_URL` to https (cookies become `Secure`).
- **Keycloak** in production mode (`start`), HA database, realm without the demo CLI client, real identity onboarding.
- **Gateway:** move to Kong (JWT plugin, per-consumer quotas, mTLS to departments) — routes and headers are already Kong-compatible.
- **Secrets:** Vault / cloud secret manager instead of `.env`.
- **Scale:** API is stateless (scale horizontally); worker consumers scale per queue; circuit breaker and rate limits are already shared via Redis.
- **Data:** managed PostgreSQL with backups/PITR; partition `audit_logs`, `connector_calls`, `events` by month; ship audit hashes to WORM storage.
- **Observability:** add Alertmanager routing for `monitoring/prometheus/alerts.yml`, log shipping (Loki/ELK), tracing (OpenTelemetry using the existing correlation ids).
- Set `DEMO_MODE=false` and replace mock department URLs/credentials with real department endpoints.
