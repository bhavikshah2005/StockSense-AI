# Database

PostgreSQL is the primary database. SQLAlchemy models live in `backend/app/models`, and the initial schema is applied with Alembic.

## Connection

PostgreSQL is hosted on Supabase. The API and Alembic both use `DATABASE_URL` from the repository `.env`. That file is gitignored. `.env.example` leaves `DATABASE_URL` empty. The React app does not receive this value.

The backend accepts `postgresql://`, `postgres://`, or `postgresql+psycopg://` and connects with psycopg. Hosted connections use `sslmode=require` when the URL does not already set it. The SQLAlchemy pool is `pool_size` 5, `max_overflow` 5, `pool_pre_ping`, and `pool_recycle` of 1800 seconds. Alembic uses a `NullPool` engine with the same URL and SSL settings.

Supabase offers three connection styles:

| Style | Host and port | Use with this app |
| --- | --- | --- |
| Direct | `db.[project-ref].supabase.co:5432` | Works with SQLAlchemy and Alembic. On the free plan the host is IPv6-only. |
| Session pooler | `aws-0-[region].pooler.supabase.com:5432`, user `postgres.[project-ref]` | Use this from machines that only have IPv4. Prepared statements work. Alembic works. |
| Transaction pooler | same host, port `6543` | Do not use for Alembic. The API falls back to `NullPool` and disables prepared statements, but migrations need a session connection. |

Put the session pooler URI, or the direct URI when IPv6 is available, in `.env` as `DATABASE_URL`.

## Tooling

| Piece | Location |
| --- | --- |
| Engine and session | `backend/app/core/database.py` |
| Models | `backend/app/models/` |
| Alembic config | `backend/alembic.ini` |
| Migration environment | `backend/alembic/env.py` |
| Revision scripts | `database/migrations/` |
| Development seed | `backend/app/db/seed.py` |

From `backend`, with the virtual environment active:

```bash
alembic upgrade head
python -m app.db.seed
```

The seed inserts a fictional user (`test.user@example.com`), the bundled NSE and BSE catalog, and a fictional symbol (`TEST_STOCK` on exchange `TEST`) that search does not return. It does not insert prices or financial metrics.

`stock_prices.interval` distinguishes bars that share a timestamp. Stored values are `1d`, `1h`, `15m`, and `5m`. A chart requests an intraday interval only when the connected provider lists it. The unique index is `(stock_id, interval, timestamp)`. Prices are `NUMERIC(18, 4)` and must be non-negative. `high` must be at least `low`, and open and close must sit inside that range. Historical sync upserts that key, so a later bar for the same instant replaces the stored OHLC and volume.

## Tables

| Table | Role |
| --- | --- |
| `users` | Accounts. Email is unique. Only `password_hash` is stored. |
| `user_sessions` | One row per signed-in device. The cookie value is stored as a SHA-256 hash. |
| `password_reset_tokens` | Single-use reset secrets, stored as SHA-256 hashes, with an expiry. |
| `stocks` | Listings. Unique on symbol + exchange. The initial catalog is India (`IN`, `INR`) on NSE and BSE. `isin` is optional. |
| `stock_prices` | OHLCV bars. Unique on stock, interval (`1d`, `1h`, `15m`, `5m`), and timezone-aware timestamp. |
| `fundamentals` | Reported financials for one listing, fiscal period, and source. `report_date` is the period end. `filing_date` is the announcement date when the provider supplies it. |
| `valuation_snapshots` | Point-in-time valuation. Unique on stock, snapshot time, and source. |
| `technical_indicators` | Named indicators plus `additional_indicators` JSONB for later names. |
| `sector_benchmarks` | Dated sector aggregates, matched to a stock by sector and country. `currency`, `source`, and `methodology` describe how the row was produced. |
| `watchlists` | Named lists owned by a user. One default per user. Deleting the user deletes these rows. |
| `watchlist_stocks` | Ordered membership. Unique per list and stock. Deleting a list deletes memberships and leaves the stock row. |
| `alerts` | User-owned price, fundamental, technical, or pattern condition. Status is `active`, `paused`, `triggered`, or `disabled`. |
| `alert_events` | One trigger. Unique `idempotency_key`. Read status does not live only here. |
| `notifications` | In-app notice for one event. `read_at` does not delete the event. |
| `notification_preferences` | One row per user. Turns in-app notifications on or off. |
| `news_articles` | Headline, source, canonical URL, publication time, and ingest time. Deduped by URL hash. |
| `news_article_stocks` | Confirmed links from an article to stock-master rows. |
| `news_sentiment` | Lexicon reading: positive, neutral, negative, or uncertain. Not a price forecast. |
| `news_ingest_runs` | One provider fetch, including not-configured and error states. |
| `portfolios` | User-owned INR portfolios. Cash and contributed capital are derived from the ledger. `archived_at` blocks new records. |
| `portfolio_transactions` | Buy and sell records. These are the source of truth for holdings. |
| `portfolio_cash_movements` | Deposits and withdrawals. Cash starts at zero. |
| `portfolio_holdings` | Derived open quantity, average cost, and remaining cost. Rewritten from transactions. Market value is not stored. |
| `user_risk_settings` | Optional planning limits for the position-size calculator. |
| `metric_thresholds` | Screening thresholds at platform, country, sector, or user scope. One active row per metric and scope. |
| `ai_analysis` | Older unused model-output table. Current research does not write this table. |
| `research_analyses` | User-owned research run: evidence references, coverage report, optional validated explanation, prompt version, and scoring version. Another user's row is not returned. |
| `backtest_runs` | User-owned historical simulation: strategy, parameters, assumptions, status, and summary. Candles stay in `stock_prices`. |
| `backtest_trades` | Simulated fills for one run. Deleting the run deletes these rows. |
| `backtest_equity_points` | Close-to-close equity, cash, shares, and drawdown for charts. |

Primary keys are UUIDs. Money and ratios use `NUMERIC`. Timestamps are `timestamptz`.

Percentage-like fundamental and benchmark fields are percentage points (`15.0` means 15%). Valuation multiples are raw multiples. Fundamental money is absolute INR, not crore or million. A null `filing_date` means the result must not be treated as known before `provider_retrieved_at`.
