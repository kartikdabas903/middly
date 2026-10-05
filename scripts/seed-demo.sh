#!/usr/bin/env bash
# Seeds predictable demo data by running the real platform pipeline against the
# mock department systems (historical 2025 records; the live demo starts at APP-2026-0001).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Seeding demo data (departments, services, workflows, connectors, users, historical scenarios)…"
docker compose exec -T backend python -m app.seed.run seed
echo "✔ Demo data ready."
echo "  Portal:   http://localhost:${FRONTEND_PORT:-3000}"
echo "  API docs: http://localhost:${GATEWAY_PORT:-8000}/docs"
