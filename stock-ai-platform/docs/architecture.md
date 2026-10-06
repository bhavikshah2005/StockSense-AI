# Architecture

StockSense AI is split into a React client and a FastAPI service. The first release covers Indian listed equities on NSE and BSE, priced in INR. Country, currency, and exchange stay on the market profile so another market can be added later without rewriting search or quotes. PostgreSQL is the system of record. Redis holds authentication rate limits and a short-lived quote cache. External market, fundamental, and news data enter only through provider interfaces.

The default market and fundamental adapters read Yahoo Finance chart and fundamentals-timeseries responses. They need no API key. Quotes are marked delayed because that feed does not publish an exact delay. A provider name other than `yahoo` still uses the unconfigured Indian adapter and returns a service error.

## Request flow

1. The frontend calls the backend over HTTP.
2. Route modules in `backend/app/api/routes` validate input and return responses. They do not contain business rules.
3. Service modules in `backend/app/services` will own application behavior.
4. Services will read and write PostgreSQL through SQLAlchemy models.
5. Services will request external data from `backend/app/data_providers`, never from vendor SDKs directly.
6. Workers will later run alert evaluation and other jobs via Redis. That package is only a placeholder.

## Repository folders

| Path | Purpose |
| --- | --- |
| `frontend/` | Vite + React + TypeScript UI. Feature UI lives under `src/components`, screens under `src/pages`, shared chrome under `src/layouts`. HTTP calls belong in `src/services`. |
| `backend/` | FastAPI app package (`app/`), dependencies, and Alembic config. |
| `backend/app/api/routes` | HTTP adapters. One module per area: auth, stocks, watchlist, metrics, alerts, news, portfolio, AI, backtests. |
| `backend/app/core` | Settings, database session, Redis client factory, JWT helpers. |
| `backend/app/models` | Future SQLAlchemy models. Only the shared declarative base is wired today. |
| `backend/app/schemas` | Pydantic request and response models. |
| `backend/app/services` | Business logic. Stubs only. |
| `backend/app/data_providers` | Vendor-facing interfaces for market data, fundamentals, and news. |
| `backend/app/ai` | Evidence packing, coverage scoring, explanation checks, and the backend model client. See `docs/ai.md`. |
| `backend/app/alerts` | Alert catalog, stored-data evaluation, and the scheduled worker. See `docs/alerts.md`. |
| `backend/app/utils` | Small shared helpers. Empty until needed. |
| `database/` | Alembic migration scripts. Schema design notes are in `docs/database.md`. |
| `workers/` | Future Redis-backed jobs (alert delivery, cache refresh). Not implemented. |
| `docs/` | Architecture, database, and API documentation. |

## Frontend source folders

| Path | Purpose |
| --- | --- |
| `src/components/dashboard` | Dashboard widgets. |
| `src/components/stocks` | Search and stock detail UI. |
| `src/components/charts` | Price and indicator charts (Recharts). |
| `src/components/metrics` | Fundamental and technical metric displays. |
| `src/components/alerts` | Alert creation and history. |
| `src/components/news` | Headlines and sentiment. |
| `src/components/research` | Stock-page research presentation. |
| `src/pages/PortfoliosPage.tsx` | Portfolio list. Detail, cash, and transactions are on the portfolio page. Position size is a separate page. |
| `src/pages/BacktestsPage.tsx` | Strategy form and saved runs. A finished run, including an insufficient-data result, is a separate page. |
| `src/pages` | Route-level screens. |
| `src/layouts` | Application shell. |
| `src/services` | API client. |
| `src/hooks` | React hooks. |
| `src/types` | Shared TypeScript types. |
| `src/utils` | Pure helpers. |

## Configuration

Settings load from environment variables. See `.env.example`. Secrets are not stored in source.

Sign-in uses a server-side session. The browser receives an HttpOnly cookie and cannot read the session secret. `GET /health` does not require a session.

## Data providers

`MarketDataProvider`, `FundamentalDataProvider`, and `NewsProvider` are abstract base classes. Services depend on those interfaces.

`get_market_data_provider` reads `MARKET_DATA_PROVIDER`:

- An empty value or `yahoo` uses `YahooMarketDataProvider`.
- Any other value uses `IndianMarketDataProvider`, which has no HTTP client.

`MARKET_DATA_API_KEY` and `MARKET_DATA_BASE_URL` are backend settings. The React app has no access to them. Yahoo chart requests use `https://query1.finance.yahoo.com` unless `MARKET_DATA_BASE_URL` is set. NSE symbols are mapped to `.NS` and BSE symbols to `.BO`.

`MarketDataProvider` exposes `get_quote`, `get_historical_prices`, and `get_market_status`. Normalized models use `Decimal` for money and timezone-aware datetimes. Vendor field names stay inside the adapter. `normalize_quote` and `normalize_bar` accept the internal field names only.

Fundamentals and news providers remain separate from market data. News uses configured RSS feeds and stays empty until `NEWS_RSS_FEEDS` is set. See `docs/news.md`. Research uses stored results from those services and calls a model only when `AI_PROVIDER`, `AI_API_KEY`, and `AI_MODEL` are set on the backend. See `docs/ai.md`.

`get_fundamental_data_provider` reads `FUNDAMENTAL_DATA_PROVIDER`:

- An empty value or `yahoo` uses `YahooFundamentalDataProvider`.
- Any other value uses `IndianFundamentalDataProvider`, which has no HTTP client.

`FUNDAMENTAL_API_KEY` and `FUNDAMENTAL_API_BASE_URL` are backend settings. They are not sent to the browser. Yahoo timeseries amounts are stored as absolute INR. Filing dates are not supplied, so availability uses `provider_retrieved_at`. ROCE, current ratio, and interest coverage stay empty because those series are not on the working timeseries contract. Vendor payloads must be renamed to the internal fields in `normalize.py` before storage. The accepted aliases are `sales` to revenue, `profit` to net income, `eps_basic` to EPS, `return_on_equity` to ROE, `return_on_capital_employed` to ROCE, and `debt_equity` to debt/equity. Unknown keys are rejected. Crore, million, and billion scales are not converted inside `normalize.py`; an adapter has to supply absolute currency units.

## Fundamental data flow

Reported statements live in `fundamentals`. Valuation multiples live in `valuation_snapshots`. A report is unique on stock, period end, fiscal period label, and source. A snapshot is unique on stock, snapshot time, and source. Upserts keep an existing number when the new payload leaves that field null.

`report_date` is the period end. `filing_date` is the announcement date when the provider sends it. A null filing date is a known limitation: backtests must not treat the figure as public at the period end, only as of `provider_retrieved_at`.

A request reads PostgreSQL first. A row newer than `FUNDAMENTAL_REPORT_STALE_HOURS` (default 168) or `FUNDAMENTAL_VALUATION_STALE_HOURS` (default 24) is returned without calling the provider. A missing or stale row calls the provider once per listing inside a process lock. Nothing stored and no provider returns `503`. A provider that returns no usable metrics returns `200` with `is_available` false. Redis keys `fundamentals:{stock_id}:latest`, `fundamentals:{stock_id}:history:{params}`, `valuation:{stock_id}:latest`, and `valuation:{stock_id}:history:{params}` use `FUNDAMENTAL_CACHE_TTL_SECONDS` (default 3600, maximum 86400). A successful write drops that listing's cached responses. Redis is not the store. If Redis is down, the process keeps the same TTL in memory.

Growth is `(current - previous) / previous` in percentage points, and only when the provider omitted it and the previous value is not zero. Net and operating margins are the profit divided by revenue when revenue is positive and the provider omitted the margin. Gross margin is stored only when the provider sends it. Revenue CAGR of 3 and 5 years is computed from annual revenue when a starting year about that far back exists and the starting revenue is positive. CFO / net profit is operating cash flow divided by net income, and is null when net income is zero. These calculations are deterministic Python. No model call is involved.

`sector_benchmarks` can hold a dated sector PE, PB, ROE, ROCE, net margin, revenue growth, debt/equity, and dividend yield, plus currency, source, and methodology. The comparison route reads that table. It does not invent a sector average from the seeded catalog.

## Market data flow

Quote request:

1. The route loads the listing and rejects anything outside the active market (NSE and BSE, country `IN`, currency `INR`).
2. `MarketDataService.get_quote` reads Redis key `market:quote:{stock_id}`.
3. A fresh cache entry is returned to every user until `MARKET_DATA_QUOTE_TTL_SECONDS` elapses. The default is 15 seconds. Values above 900 seconds are rejected at startup.
4. A cache miss calls `MarketDataProvider.get_quote` once for that listing, validates the quote, stores it, and returns it. A process lock collapses concurrent misses in one API process.
5. `fetched_at` is the time the backend accepted the quote. `market_timestamp` is the provider's trade time. The UI prints both in `Asia/Kolkata`. A delayed feed sets `delayed` and, when the provider sends it, `delay_minutes`.

Historical request:

1. `GET /api/stocks/{stock_id}/prices` reads `stock_prices` only.
2. `sync_historical_prices` asks the provider for one interval and upserts `(stock_id, interval, timestamp)`.
3. The first sync requires a start date. A later sync with no start resumes at the latest stored bar's IST date, so the full history is not requested again.
4. Supported storage intervals are `1d`, `1h`, `15m`, and `5m`. The provider's `supported_intervals` decides which of those can be fetched. The Yahoo adapter supports all four.
5. No web process scheduler downloads the NSE or BSE universe. A future worker can call `sync_historical_prices`.

Chart history uses `GET /api/stocks/{stock_id}/history`. The backend turns `1d`, `1w`, `1m`, `3m`, `6m`, `1y`, `3y`, `5y`, and `max` into an Asia/Kolkata date window. `max` is today minus `MARKET_DATA_MAX_HISTORY_YEARS` (default 10). The page loads `1y` first and requests another range only when that button is selected.

The service reads `stock_prices` before calling a provider. A missing head, a gap longer than six calendar days, or a tail more than four calendar days behind the requested end is fetched and upserted. Weekend and short-holiday holes are left as the sessions the provider returned. The API does not insert Saturday or Sunday bars on its own. Intraday intervals are limited to 10 calendar days and are used for a `1d` chart only when the connected provider lists `5m`, `15m`, or `1h`. The Yahoo adapter lists those intervals. A provider with an empty interval list returns the configuration error when new bars are required. Stored bars are still returned when they already cover the window.

Responses are cached at `market:history:{stock_id}:{interval}:{start}:{end}` for `MARKET_DATA_HISTORY_TTL_SECONDS` (default 300, maximum 3600). A repeated range click uses Redis, then PostgreSQL. The provider runs only for a span that is not already stored. At most 3000 bars are returned, keeping the latest rows. `market_timestamp` is the last bar. `fetched_at` is when this response was built. Both are shown in Asia/Kolkata. The page does not call the session open or closed unless `GET /api/markets/{exchange}/status` returns a session.

The React chart is `StockPriceChart`, a Recharts close-price area with a volume panel under it. Tooltips read the OHLC fields. The same point shape can feed a candlestick view later. Range return, period high, and period low are computed in `history_math` from the stored closes, highs, and lows.

Market session:

`GET /api/markets/{exchange}/status` returns a session only when the provider reports one. The Yahoo adapter reads the `^NSEI` or `^BSESN` chart session window and the quote time. It does not decide open or closed from the server clock. An unconfigured provider returns no session.

Validation rejects negative prices, negative volume, a high below the low, a price outside the high-low range, a naive timestamp, and a symbol or exchange that does not match the listing. Those responses use a fixed public message. Logs record the error code and provider name, not the API key and not the provider body.

Provider failures map to HTTP 502 (unavailable, timeout, rejected credentials, malformed payload), 429 (provider rate limit), 404 (unknown listing), 422 (unsupported exchange or interval), and 503 (provider or calendar not configured). The browser shows "Market data is temporarily unavailable." for provider failures and does not substitute a zero price.

If Redis is down, the API keeps a process-local quote cache with the same TTL and logs one warning. PostgreSQL remains the store for OHLCV bars.

## Redis

`app.core.redis.get_redis` creates a client from `REDIS_URL`. Current uses:

- authentication rate limits
- quote cache key `market:quote:{stock_id}` with `MARKET_DATA_QUOTE_TTL_SECONDS`
- history cache key `market:history:{stock_id}:{interval}:{start}:{end}` with `MARKET_DATA_HISTORY_TTL_SECONDS`
- fundamental and valuation response caches with `FUNDAMENTAL_CACHE_TTL_SECONDS`

Watchlist names, membership, and order live in PostgreSQL. Those responses are not cached in Redis. A watchlist page reuses the shared quote cache, so a missing quote stays unavailable and is never filled with a placeholder price.

Metric thresholds are stored in PostgreSQL and are not cached in Redis. Evaluation reads stored metric rows for the requested stock. It does not create alert events.

Background job runners are still a later stage. Redis is not the system of record for prices, watchlists, or thresholds.

## Database

SQLAlchemy 2.0 style sessions live in `app.core.database`. PostgreSQL is the Supabase database named by `DATABASE_URL`. Alembic uses that same URL. Redis stays local through Docker Compose. The domain tables are defined in `backend/app/models` and described in `docs/database.md`.
