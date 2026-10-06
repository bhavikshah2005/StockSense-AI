# Deployment

The site, API, and worker all run on Render. PostgreSQL stays on Supabase, and Redis is a managed instance. Applying these files does not by itself create those accounts. Nothing here has been deployed from this repository pass.

## Required production settings

Set these on the API and the worker. Do not put them in `VITE_*` variables or in the frontend bundle.

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | Yes | `production`. The process refuses to start when the checks below fail. |
| `DATABASE_URL` | Yes | Supabase session pooler, port 5432, `sslmode=require`. Do not use the transaction pooler (port 6543) for Alembic. |
| `REDIS_URL` | Yes | `rediss://` URL for managed Redis. A local hostname is rejected in production. |
| `FRONTEND_URL` | Yes | Comma-separated `https` origins of the frontend. This is the CORS allow-list and the CSRF origin check. |
| `COOKIE_SECURE` | Yes | `true`. |
| `COOKIE_SAMESITE` | Yes | `none` for the Render site and API, because they are separate services. `lax` only if both are later served from one site. `none` requires `COOKIE_SECURE=true`. |

The session cookie is `HttpOnly`, path `/`, and is not readable by JavaScript. Logout deletes the server session. Unsafe browser methods must send an `Origin` that is in `FRONTEND_URL`. Requests with no `Origin` are allowed for non-browser clients.

Optional and safe to leave empty: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `NEWS_PROVIDER`, `NEWS_RSS_FEEDS`, `EMAIL_PROVIDER_API_KEY`. Yahoo market data needs `MARKET_DATA_PROVIDER=yahoo` and no key. Empty news or AI shows a configuration-required state. The app still starts.

`VITE_API_BASE_URL` is the only frontend setting. It is the public API origin, built into the static app. It must not contain a database URL, Redis URL, or provider key.

## Frontend

`render.yaml` defines a Render static site named `stocksense-web`. Root directory: `frontend`. Build command: `npm ci && npm run build`. Publish directory: `dist`. A rewrite sends every path to `index.html` so a refresh on a client route still loads the app.

Set `VITE_API_BASE_URL` to the Render API origin before the build. The browser calls only that API, with credentials. It does not call Yahoo, OpenAI, or Supabase directly.

Set the API `FRONTEND_URL` to this site's `https` origin. The two Render hosts are different sites, so the API cookie stays `SameSite=None` and `Secure`.

## API

From `backend`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips $FORWARDED_ALLOW_IPS
```

`render.yaml` uses this shape. Set `FORWARDED_ALLOW_IPS=*` only when the platform proxy is the sole public path, as on Render. Do not use that value on a host where clients can reach the process directly. The health check path is `/live`.

Do not run `python -m app.db.seed` in production. Apply migrations as a release step, not on every API boot. The API does not create tables at startup.

## Worker

```bash
python -m app.workers.supervisor
```

That process runs the alert, news, and backtest loops. Each loop uses a Postgres advisory lock so a second copy does not double-apply the same pass. Alert and news jobs stay idempotent through their existing keys. A backtest that already finished is not written twice.

The same `DATABASE_URL` and `REDIS_URL` are required. News ingest stays idle until `NEWS_PROVIDER` and `NEWS_RSS_FEEDS` are set.

## Database

1. Take a Supabase backup or snapshot.
2. From `backend`, with `DATABASE_URL` pointing at the session pooler: `alembic upgrade head`.
3. Review the migration before applying it. The current chain ends at `d5e0f3c92b60`.
4. Roll back application code if a migration must be reversed only when that migration's `downgrade()` is known to be safe. Prefer a forward fix when a migration has already been applied to production.

Connection pooling in the API is small (5 connections, overflow 5) so a session pooler is not exhausted. Recycle is 30 minutes.

## Redis

Redis holds rate-limit counters and short-lived market caches. User records stay in PostgreSQL. If Redis is down, rate limits fall back to the API process and caches miss. Readiness still passes when PostgreSQL is up. Restore Redis by setting `REDIS_URL` and restarting the API and worker.

## Health

| Path | Meaning |
| --- | --- |
| `GET /live` | The process is running. No dependency check. |
| `GET /ready` | PostgreSQL must answer. Redis is `ok` or `unavailable` and does not fail the check. |
| `GET /health` | PostgreSQL only. `degraded` and HTTP 503 when it does not answer. |

Responses do not include connection strings. Unhandled errors return a generic message and a `X-Request-ID` header. Details stay in server logs. Production hides `/docs`.

## Backups

Supabase point-in-time recovery or daily backups must be turned on in the Supabase project. This repository cannot enable that. Redis can be rebuilt from an empty instance. Provider history is not a backup of user portfolios or backtests.

## Smoke test after a release

Sign in on the production origin, refresh, open a stock, and sign out. Call `GET /ready`. Confirm a protected route returns 401 after logout. Confirm news and AI show their real configuration state rather than sample content.

## Incident notes

- API 503 on `/ready` with `database: unavailable`: check `DATABASE_URL`, the pooler, and Supabase status. Do not point the app at a new empty database without a restore.
- Sign-in works locally but the deployed site stays logged out: the Render site and API are different hosts. Use `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`, and the exact `https` site origin in `FRONTEND_URL`.
- Repeated alert or news rows: confirm only one worker holds the advisory lock and that a retry is using the existing idempotency key.
- A provider error on one stock page should leave watchlists, portfolios, and the rest of the API usable.
