#!/usr/bin/env bash
# Installs everything needed for Middly development:
#   .env, backend venv + dev deps, frontend deps, Playwright browser, Docker images.
set -euo pipefail
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null 2>&1 || { echo "✗ $1 is required ($2)"; exit 1; }; }
need docker "https://docs.docker.com/get-docker/"
need node "Node.js 20.9+"
need npm "comes with Node.js"
PY=""
for c in python3.11 python3 python py; do  # on Windows "python3" may be a non-working Store alias
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; assert sys.version_info >= (3, 11)" >/dev/null 2>&1; then PY="$c"; break; fi
done
[[ -n "$PY" ]] || { echo "✗ Python 3.11+ is required"; exit 1; }

echo "▶ 1/5 Environment file"
[[ -f .env ]] && echo "  .env exists — kept" || ./scripts/init-env.sh

echo "▶ 2/5 Backend virtualenv (backend/.venv) + dev dependencies"
"$PY" -m venv backend/.venv
if [[ -f backend/.venv/bin/python ]]; then VPY=backend/.venv/bin/python; else VPY=backend/.venv/Scripts/python; fi
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q -r backend/requirements-dev.txt

echo "▶ 3/5 Frontend dependencies"
(cd frontend && npm install --no-audit --no-fund)

echo "▶ 4/5 Playwright browser (Chromium)"
(cd frontend && npx playwright install chromium)

echo "▶ 5/5 Docker images"
docker compose build

echo
echo "✔ Development environment ready."
echo "  Start the stack:        ./scripts/start.sh"
echo "  Live-reload backend:    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d"
echo "  Unit tests (local):     backend/.venv/*/python -m pytest -m 'not integration'   (run from backend/)"
echo "  All tests:              ./scripts/test.sh"
