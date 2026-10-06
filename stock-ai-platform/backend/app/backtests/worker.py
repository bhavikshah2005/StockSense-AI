"""Run queued backtests.

From the backend directory:

    python -m app.backtests.worker

The interval is BACKTEST_WORKER_INTERVAL_SECONDS (default 30, between 5 and 300).
PostgreSQL stores the run. A Postgres advisory lock stops two workers from
claiming work together. Redis is not the store for runs or results.
"""

from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.backtest_service import process_queued

logger = logging.getLogger(__name__)


def run_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        return process_queued(db)
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    interval = settings.backtest_worker_interval_seconds
    logger.info("backtest worker started interval_seconds=%s", interval)
    while True:
        try:
            logger.info("backtest worker %s", run_once())
        except Exception:
            logger.exception("backtest worker failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
