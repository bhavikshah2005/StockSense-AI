"""Run the existing workers in one process.

From the backend directory:

    python -m app.workers.supervisor

Each loop keeps its own interval and Postgres advisory lock. A failure in one
loop is logged and does not stop the others. Redis is not the job store.
"""

from __future__ import annotations

import logging
import threading

from app.alerts.worker import main as run_alerts
from app.backtests.worker import main as run_backtests
from app.news.worker import main as run_news

logger = logging.getLogger(__name__)


def _guard(name: str, target) -> None:  # type: ignore[no-untyped-def]
    try:
        target()
    except Exception:
        logger.exception("worker stopped name=%s", name)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    threads = [
        threading.Thread(target=_guard, args=("alerts", run_alerts), name="alerts", daemon=True),
        threading.Thread(target=_guard, args=("news", run_news), name="news", daemon=True),
        threading.Thread(target=_guard, args=("backtests", run_backtests), name="backtests", daemon=True),
    ]
    for thread in threads:
        thread.start()
    logger.info("worker supervisor started")
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
