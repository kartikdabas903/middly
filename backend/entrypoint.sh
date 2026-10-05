#!/bin/sh
set -e

wait_for_db() {
  python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.core.config import get_settings
url = get_settings().database_url
for attempt in range(60):
    try:
        with create_engine(url).connect() as c:
            c.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception as exc:
        print(f"waiting for database ({exc.__class__.__name__})", flush=True)
        time.sleep(2)
sys.exit(1)
PY
}

case "$1" in
  api)
    wait_for_db
    alembic upgrade head
    if [ "${SEED_ON_STARTUP:-true}" = "true" ]; then
      python -m app.seed.run seed-if-empty
    fi
    RELOAD=""
    if [ "${UVICORN_RELOAD:-false}" = "true" ]; then RELOAD="--reload --reload-dir /app/app"; fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --no-access-log $RELOAD
    ;;
  worker)
    wait_for_db
    exec python -m app.worker
    ;;
  migrate)
    wait_for_db
    exec alembic upgrade head
    ;;
  seed)
    shift
    exec python -m app.seed.run "${@:-seed}"
    ;;
  test)
    shift
    exec python -m pytest "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
