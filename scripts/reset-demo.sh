#!/usr/bin/env bash
# Wipes all platform data (schema is kept), resets the mock department systems,
# circuit breakers, caches and RabbitMQ queues. Run ./scripts/seed-demo.sh afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Resetting Middly demo environment…"
docker compose exec -T backend python -m app.seed.run reset
echo "✔ Reset complete. Now run ./scripts/seed-demo.sh"
