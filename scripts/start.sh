#!/usr/bin/env bash
# One-command start: creates .env if missing, builds and starts all services, waits for health.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -f .env ]] || ./scripts/init-env.sh
docker compose up -d --build

echo "▶ Waiting for services to become healthy…"
for i in $(seq 1 90); do
  unhealthy=$(docker compose ps --format '{{.Service}} {{.Health}}' | awk '$2 != "healthy" && $2 != "" {print $1}')
  if [[ -z "$unhealthy" ]]; then
    echo "✔ All services healthy"
    break
  fi
  sleep 5
done
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
echo
echo "  Portal:     http://localhost:${FRONTEND_PORT:-3000}"
echo "  API docs:   http://localhost:${GATEWAY_PORT:-8000}/docs"
echo "  Keycloak:   http://localhost:${KEYCLOAK_PORT:-8080}"
echo "  Grafana:    http://localhost:${GRAFANA_PORT:-3001}"
echo "  Prometheus: http://localhost:${PROMETHEUS_PORT:-9090}"
echo "  RabbitMQ:   http://localhost:${RABBITMQ_MGMT_PORT:-15672}"
