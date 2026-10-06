"""Evaluate active alerts on a timer.

Run locally from the backend directory:

    python -m app.alerts.worker

The interval is ALERT_EVAL_INTERVAL_SECONDS (default 300, between 30 and 3600).
PostgreSQL is the source of truth. A Postgres advisory lock stops two workers
from evaluating the same pass. Trigger inserts also use an idempotency key, so
a retry does not create a second event. This process reads stored prices,
fundamentals, indicators, and patterns. It does not download new market data
and it does not decide that the market is open from the server clock.
"""

from __future__ import annotations

import logging
import time

from app.alerts.evaluator import evaluate_active
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def run_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        return evaluate_active(db)
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    interval = settings.alert_eval_interval_seconds
    logger.info("alert worker started interval_seconds=%s", interval)
    while True:
        try:
            result = run_once()
            logger.info("alert evaluation %s", result)
        except Exception:
            logger.exception("alert evaluation failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
