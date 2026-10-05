"""CLI: python -m app.seed.run [seed|reset|reset-and-seed|seed-if-empty]"""
from __future__ import annotations

import logging
import sys
import time

import httpx

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.seed import demo

logger = logging.getLogger("seed")

MOCKS = ["http://mock-identity:8000", "http://mock-education:8000", "http://mock-employment:8000", "http://mock-skill:8000", "http://mock-grievance:8000"]


def wait_for_mocks(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    pending = list(MOCKS)
    while pending and time.time() < deadline:
        for url in list(pending):
            try:
                if httpx.get(url + "/health", timeout=2).status_code < 500:
                    pending.remove(url)
            except Exception:
                pass
        if pending:
            time.sleep(2)
    if pending:
        raise SystemExit(f"Mock systems not reachable: {pending}")


def main(argv: list[str]) -> None:
    configure_logging(get_settings().log_level)
    cmd = argv[1] if len(argv) > 1 else "seed"
    if cmd in ("seed", "reset-and-seed", "seed-if-empty"):
        wait_for_mocks()
    if cmd == "reset":
        demo.reset()
    elif cmd == "seed":
        demo.seed()
    elif cmd == "reset-and-seed":
        demo.reset()
        demo.seed()
    elif cmd == "seed-if-empty":
        if demo.is_seeded():
            logger.info("Database already contains data; skipping seed")
        else:
            demo.seed()
    else:
        raise SystemExit(f"Unknown command {cmd}")


if __name__ == "__main__":
    main(sys.argv)
