"""Ingest configured Indian news feeds.

Run locally from the backend directory:

    python -m app.news.worker

The interval is NEWS_INGEST_INTERVAL_SECONDS (default 900, between 60 and 86400).
With NEWS_RSS_FEEDS empty, each pass records not_configured and stores nothing.
This is not a live feed. Freshness is the last successful ingest time.
"""

from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.core.database import SessionLocal
from app.data_providers.news import get_news_provider
from app.news.ingest import ingest

logger = logging.getLogger(__name__)


def run_once() -> dict[str, int | str]:
    db = SessionLocal()
    try:
        return ingest(db, get_news_provider())
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    interval = settings.news_ingest_interval_seconds
    logger.info("news worker started interval_seconds=%s provider=%s", interval, get_news_provider().name)
    while True:
        try:
            logger.info("news ingest %s", run_once())
        except Exception:
            logger.exception("news ingest failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
