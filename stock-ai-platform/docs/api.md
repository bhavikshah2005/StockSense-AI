# API

The backend is a FastAPI application in `backend/app/main.py`. Interactive docs are served by FastAPI at `/docs` when the server is running.

Authentication uses an HttpOnly session cookie named `stocksense_session`. The API stores only a SHA-256 hash of that cookie in `user_sessions`, so a database copy cannot be replayed. Each login creates a separate session, so one account can stay signed in on more than one device. Logout revokes the presented session. A password change revokes the other sessions and rotates the current cookie. Password reset revokes every session.

The cookie is not placed in browser storage. The React app calls the API with `credentials: "include"`. `FRONTEND_URL` is the allowlist for CORS and for cross-site write requests. When the frontend and API are different sites, set `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`. Same-site development (both on `localhost`, or both on `127.0.0.1`) can use `COOKIE_SAMESITE=lax`.

Password reset email delivery is not connected. `PendingEmailSender` records that a message was not sent and does not log the reset URL. Set `EMAIL_PROVIDER_API_KEY` only after a provider is implemented.

Interactive docs at `/docs` list authentication, Indian stock search, listing detail, quotes, stored prices, reported fundamentals, valuation snapshots, sector comparison, and market status. News, alerts, and AI routes are still empty.

Market-data and fundamental credentials stay on the API. The React app never receives `MARKET_DATA_API_KEY` or `FUNDAMENTAL_API_KEY`.

## GET /api/stocks/search

Requires the session cookie. `q` matches an Indian symbol, company name, or ISIN on the active market (NSE and BSE).

```json
{
  "query": "TCS",
  "results": [
    {
      "symbol": "TCS",
      "company_name": "Tata Consultancy Services Limited",
      "exchange": "NSE",
      "sector": "Information Technology",
      "industry": "IT Services",
      "currency": "INR",
      "country": "IN",
      "country_name": "India",
      "isin": "INE467B01029"
    }
  ]
}
```

Search results include `id`. Open `/stocks/{id}` in the app to request a quote.

## GET /api/stocks/{stock_id}

Requires the session cookie. Returns one NSE or BSE listing and no prices. An unknown id is `404`. A listing outside the active market is `422`.

## GET /api/stocks/{stock_id}/quote

Requires the session cookie. Returns the cached quote or loads it through `MarketDataProvider`. Money is a decimal string. `market_timestamp` is the provider's trade time. `fetched_at` is when this API stored the quote. `delayed` is true when the provider marks the feed as delayed.

An empty `MARKET_DATA_PROVIDER` or the value `yahoo` uses the Yahoo chart adapter. Any other provider name, or the unconfigured adapter used in tests, returns `503`:

```json
{ "detail": "Market data service temporarily unavailable" }
```

The body contains no price and no credential. Other provider failures use `502` with "Market data provider unavailable", or `429` with "Market data rate limit reached".

A configured adapter that returns a quote uses this shape:

```json
{
  "stock_id": "...",
  "symbol": "TCS",
  "exchange": "NSE",
  "currency": "INR",
  "current_price": "3452.5000",
  "previous_close": "3418.2000",
  "change": "34.3000",
  "change_percent": "1.0035",
  "open": "3420.0000",
  "high": "3465.0000",
  "low": "3410.0000",
  "volume": 1234567,
  "market_timestamp": "2026-09-23T05:01:00Z",
  "fetched_at": "2026-09-23T05:01:03Z",
  "delayed": true,
  "delay_minutes": 15
}
```

The same cached payload is reused for every user until `MARKET_DATA_QUOTE_TTL_SECONDS` expires.

## GET /api/stocks/{stock_id}/prices

Requires the session cookie. Query `interval` (`1d`, `1h`, or `15m`), plus optional `start` and `end` dates. Dates are interpreted in `Asia/Kolkata`. The route returns bars already stored in `stock_prices`. It does not call the provider. An empty `bars` list means nothing has been synced.

`sync_historical_prices` in `backend/app/services/market_data_service.py` is the ingestion entry point for a future worker. It upserts on stock, interval, and timestamp.

## GET /api/stocks/{stock_id}/history

Requires the session cookie. Send either `range` or both `start_date` and `end_date`.

`range` is one of `1d`, `1w`, `1m`, `3m`, `6m`, `1y`, `3y`, `5y`, `max`. The API converts that name into an Asia/Kolkata window ending today. `max` starts `MARKET_DATA_MAX_HISTORY_YEARS` ago. Optional `interval` is `1d`, `1h`, `15m`, or `5m`. When it is omitted, ranges other than `1d` use daily bars. A `1d` range uses `5m`, then `15m`, then `1h`, when the connected provider lists that interval. The current provider lists none.

Intraday requests longer than 10 days are `422`. A start after the end, an unknown range, or a window past the configured maximum is `422` with "The requested date range is invalid". An unknown listing is `404`. A provider failure is `502` or `429`. No configured adapter is `503`.

An empty `data` array means the provider returned no sessions for that window. Missing weekends are not filled in.

```json
{
  "stock": {
    "id": "...",
    "symbol": "TCS",
    "company_name": "Tata Consultancy Services Limited",
    "exchange": "NSE",
    "currency": "INR"
  },
  "interval": "1d",
  "range": "1y",
  "start_date": "2025-09-23",
  "end_date": "2026-09-23",
  "market_timestamp": "2026-09-23T03:45:00Z",
  "fetched_at": "2026-09-23T05:01:03Z",
  "data": [
    {
      "timestamp": "2026-09-23T03:45:00Z",
      "open": "3420.0000",
      "high": "3465.0000",
      "low": "3410.0000",
      "close": "3450.0000",
      "adjusted_close": "3450.0000",
      "volume": 1234567
    }
  ],
  "performance": {
    "start_price": "3100.0000",
    "end_price": "3450.0000",
    "change": "350.0000",
    "change_percent": "11.2903"
  },
  "period_high": "3800.0000",
  "period_low": "2900.0000"
}
```

`performance` uses the first close and the last close. `period_high` and `period_low` are the maximum high and minimum low in the returned bars. Money is a decimal string.

The same response is cached in Redis for `MARKET_DATA_HISTORY_TTL_SECONDS`. A later request for a window already stored in PostgreSQL does not call the provider.

## GET /api/markets/{exchange}/status

Requires the session cookie. `exchange` is `NSE` or `BSE`. The Yahoo adapter returns `open`, `pre-open`, `post-market`, or `closed` from the index chart session window. An unconfigured provider returns `503`. The API does not answer from the server's local clock.

## GET /api/stocks/{stock_id}/fundamentals

Requires the session cookie. Returns the newest reported financial period stored for that NSE or BSE listing.

Money is an absolute amount in the listing currency (INR rupees). Growth, margins, ROE, and ROCE are percentage points. When the provider leaves a growth or margin empty and the prior period has the inputs, the API fills it with the formulas in `fundamental_math`. A zero or negative revenue denominator is left null. A missing filing date means the publication time is unknown; `provider_retrieved_at` is then the only availability timestamp.

An empty `FUNDAMENTAL_DATA_PROVIDER` or the value `yahoo` uses the Yahoo timeseries adapter. `503` means a non-Yahoo provider name is set and nothing is stored. `200` with `metadata.is_available` false means the provider returned no usable figures. The body does not contain invented ratios.

## GET /api/stocks/{stock_id}/fundamentals/history

Requires the session cookie. Query parameters: `start_date`, `end_date`, `period` (`annual` or `quarterly`), `limit` (1–100), and `offset`. Results are chronological. Each historical row's CAGR uses only reports that do not post-date that row.

## GET /api/stocks/{stock_id}/valuation

Requires the session cookie. Returns the newest valuation snapshot. Multiples are raw. Dividend yield is percentage points. These figures are not stored on the financial report because they move with the price.

## GET /api/stocks/{stock_id}/valuation/history

Requires the session cookie. Query parameters: `start_date`, `end_date`, `limit` (1–100), and `offset`.

## GET /api/stocks/{stock_id}/sector-comparison

Requires the session cookie. Compares stored stock metrics with a `sector_benchmarks` row for the same sector and country. Missing benchmarks are null. The response is not a recommendation.

## GET /api/stocks/{stock_id}/technical-analysis

Requires the session cookie. Query parameters: `interval` (`1d` only), `start_date`, and `end_date`. The default window is 800 calendar days and the maximum is 1100.

The body contains the indicator snapshot, a close and moving-average series, detected patterns, support and resistance zones, breakout evidence, and a conclusion. The conclusion category is `bullish_evidence`, `bearish_evidence`, `mixed_evidence`, `no_clear_direction`, or `insufficient_data`. It is not a forecast or a trade instruction. Rules are in `docs/technical-analysis.md`.

`503` means no daily bars are stored and the market-data provider is not configured. An unsupported interval or an invalid date window is `422`.

## GET /api/stocks/{stock_id}/technical-analysis/patterns

Requires the session cookie. Filters: `interval`, `pattern_type`, `status`, `start_date`, `end_date`, `limit` (1–50), and `offset`. Results are persisted pattern rows for detector version `patterns-1`.

## GET /api/stocks/{stock_id}/technical-analysis/summary

Requires the session cookie. Returns the conclusion, freshness, and the price timestamp used.

## GET /health

Confirms the API process can run a query against PostgreSQL.

Response `200`:

```json
{
  "status": "ok",
  "database": "ok"
}
```

If PostgreSQL cannot be reached, the response is `503` with `status` `degraded` and `database` `unavailable`. The body does not include the connection string or the database error. Redis is not checked. Authentication is not required.

## Watchlists

Every watchlist route requires the session cookie. The server uses that session's user. A `user_id` in the request is ignored. Another user's watchlist id returns `404` with `Watchlist not found`.

Limits come from settings: `WATCHLIST_MAX_LISTS` (20), `WATCHLIST_MAX_STOCKS` (50), `WATCHLIST_NAME_MAX_LENGTH` (80), and `WATCHLIST_DESCRIPTION_MAX_LENGTH` (280). Names are trimmed. The same user cannot reuse a name, ignoring case. The first watchlist is the default. Setting a new default clears the previous one. Deleting the default promotes the remaining list with the lowest sort order.

Membership is unique per watchlist. The same stock may sit on more than one of the user's lists. Reorder replaces the full order and must include each current stock id once. Deleting a watchlist deletes its membership rows and leaves the stock catalog row.

`GET /api/watchlists/{id}` attaches the cached quote for each stock. `available` is false, with null prices, when the provider has no quote. `delayed`, `source`, `market_timestamp`, and `fetched_at` describe freshness. A delayed quote is not described as live. Watchlist rows themselves are not stored in Redis.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/watchlists` | The user's lists, with stock counts. `?stock_id=` adds `contains_stock`. |
| POST | `/api/watchlists` | Create `{ "name", "description" }`. `201`. |
| GET | `/api/watchlists/{id}` | Metadata, ordered stocks, and quotes when available. |
| PATCH | `/api/watchlists/{id}` | Rename or change the description. |
| DELETE | `/api/watchlists/{id}` | `204`. Stocks remain. |
| POST | `/api/watchlists/{id}/stocks` | `{ "stock_id" }` for an active NSE or BSE listing. |
| DELETE | `/api/watchlists/{id}/stocks/{stock_id}` | `204`. Removes the membership only. |
| PATCH | `/api/watchlists/{id}/stocks/order` | `{ "stock_ids": [...] }` exact current membership. |
| PATCH | `/api/watchlists/{id}/default` | Makes this the only default. |

Validation uses `422`. A duplicate name or stock uses `409`. An unknown watchlist or stock uses `404`.

## Metric thresholds

Every metrics route requires the session cookie. The server uses that session's user. A `user_id` in the request is ignored. Another user's threshold id returns `404`.

Platform, India-market, and sector rows are readable and cannot be changed through these routes. A user may create, update, disable, and delete only their own rows. `THRESHOLD_MAX_USER_OVERRIDES` (default 100) caps how many rows one user may store.

Precedence is user-for-this-stock, user-for-all-stocks, matching sector, matching market, then platform. A disabled row or a row outside its effective dates is skipped. Two active rows at the same scope are rejected on write. Evaluation reads stored fundamentals, valuations, sector benchmarks, and indicator rows. It does not call a provider and does not invent a missing value. Stale stored values return `stale_data` and are not treated as met. A crossing needs the previous stored reading. Details are in `docs/metrics.md`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/metrics/registry` | Supported metrics, operators, and `metrics-1`. |
| GET | `/api/metrics/thresholds` | Defaults plus the user's rows. Optional `metric_key` and `stock_id`. |
| POST | `/api/metrics/thresholds` | Create a user threshold. `201`. |
| PATCH | `/api/metrics/thresholds/{id}` | Update a user-owned threshold, including `is_active`. |
| DELETE | `/api/metrics/thresholds/{id}` | `204`. |
| POST | `/api/metrics/evaluate` | `{ "stock_id", "metric_keys" }`. One result per metric. |

Validation uses `422`. A duplicate active user threshold uses `409`.

## Alerts and notifications

Every alerts and notifications route requires the session cookie. The server uses that session's user. A `user_id` in the request is ignored. Another user's alert or notification returns `404`. There is no route that marks an alert as triggered.

Evaluation and preview read stored data only. Preview does not insert an event. Details, including repeat and re-arm behavior, are in `docs/alerts.md`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/alerts/catalog` | Supported price, fundamental, technical, and pattern conditions. |
| GET | `/api/alerts` | The user's alerts. `limit` and `offset`. |
| POST | `/api/alerts` | Create an alert. `201`. |
| GET | `/api/alerts/{id}` | One owned alert. |
| PATCH | `/api/alerts/{id}` | Update the condition or note. History is kept. |
| DELETE | `/api/alerts/{id}` | `204`. |
| POST | `/api/alerts/{id}/pause` | Pause an active alert. |
| POST | `/api/alerts/{id}/resume` | Resume a paused or triggered alert and arm it again. |
| GET | `/api/alerts/{id}/events` | Trigger history. `limit` and `offset`. |
| POST | `/api/alerts/{id}/preview` | Current stored comparison. Does not create a trigger. |
| GET | `/api/notifications` | In-app inbox. Optional `unread=true`. |
| POST | `/api/notifications/read` | Mark every notification read. |
| POST | `/api/notifications/{id}/read` | Mark one notification read. |
| GET | `/api/notifications/preferences` | In-app preference and email availability. |
| PATCH | `/api/notifications/preferences` | `{ "in_app_enabled": true }`. Delivery is in the app only. |

Example create:

```json
{
  "stock_id": "10c53c6a-609d-4663-b02f-71d741b22439",
  "category": "price",
  "metric": "price",
  "operator": ">",
  "threshold_type": "absolute",
  "threshold_value": "4000",
  "repeat_mode": "once"
}
```

Validation uses `422`. An unknown stock uses `404`.

## Planned route modules

| Module | Prefix | Planned responsibility |
| --- | --- | --- |
| `auth.py` | `/api/auth` | Registration, login, logout, session, and password reset. |
| `users.py` | `/api/users` | The signed-in user's profile. |
| `stocks.py` | `/api/stocks` | Indian listing search, listing detail, quotes, stored OHLCV bars, fundamentals, valuation, sector comparison, and technical analysis. |
| `markets.py` | `/api/markets` | Indian session status when a provider or calendar supplies it. |
| `watchlist.py` | `/api/watchlists` | Implemented. See Watchlists above. |
| `metrics.py` | `/api/metrics` | Implemented. See Metric thresholds above. |
| `alerts.py` | `/api/alerts` | Implemented. See Alerts and notifications above. |
| `news.py` | `/api/news` | Implemented. See `docs/news.md`. |
| `portfolio.py` | `/api/portfolios` | Implemented. See `docs/portfolio.md`. |
| `ai.py` | `/api/ai` | Implemented. See `docs/ai.md`. |
| `backtests.py` | `/api/backtests` | Implemented. See `docs/backtesting.md`. |

Business rules will live in `backend/app/services`, not in these modules.
