# Workers

Alert evaluation runs in the API process tree, not in this folder:

```bash
cd backend
python -m app.alerts.worker
```

It reads stored rows, writes trigger events to PostgreSQL, and sleeps for `ALERT_EVAL_INTERVAL_SECONDS`. It does not call a market-data provider and it does not use Redis as the alert record. Two copies coordinate with a PostgreSQL advisory lock. See `docs/alerts.md`.

Redis remains the cache and rate-limit store for the API. It is not a queue for alerts.

News ingestion is a separate process:

```bash
cd backend
python -m app.news.worker
```

It reads `NEWS_RSS_FEEDS` and writes articles to PostgreSQL. An empty feed list stores nothing. See `docs/news.md`.
