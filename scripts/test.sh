#!/usr/bin/env bash
# Runs the backend unit + integration tests (inside the stack) and the Playwright E2E demo.
#   ./scripts/test.sh            # backend + e2e
#   ./scripts/test.sh backend    # backend only
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Backend tests (pytest: unit + integration against an isolated test database)"
docker compose exec -T backend python -m pytest -q

if [[ "${1:-all}" != "backend" ]]; then
  echo "▶ End-to-end demo (Playwright; resets demo data first)"
  (cd frontend && npx playwright test)
  echo "  Note: demo data now reflects the E2E run — run ./scripts/reset-demo.sh && ./scripts/seed-demo.sh before presenting."
fi
echo "✔ All tests passed"
