# Production readiness audit

Audit date: 2026-09-25. The product modules below were already implemented and covered by their own tests. This pass did not replace them.

## Module status

| Area | Status | Notes |
| --- | --- | --- |
| Auth and profiles | Complete | HttpOnly session cookie, Argon2, logout deletes the server session. Origin check is the CSRF control. |
| Indian stock master, quotes, history, charts | Complete | Yahoo when configured. Missing data stays unavailable. |
| Fundamentals and technical analysis | Complete | Stored or provider-backed. Conclusions are not forecasts. |
| Watchlists | Complete | User-scoped. |
| Thresholds | Complete | Shared metric registry. Insufficient data is a real state. |
| Alerts and in-app notifications | Complete | No email channel. Worker plus advisory lock. |
| News and sentiment | Complete | Empty until RSS is configured. Untrusted HTML is not rendered as markup. |
| AI research | Complete | Unavailable until `AI_PROVIDER` is set. No numeric buy/sell score. |
| Portfolios and position size | Complete | Transactions are the ledger. The size calculator does not place trades. |
| Backtesting | Complete | Stored daily bars, long-only, explicit costs. No benchmark series. |
| Deployment and CI | Was missing | Added in this pass. Not executed against live hosts. |

## Findings and fixes

| Priority | Finding | Fix |
| --- | --- | --- |
| High | No production setting check. A host could boot with an insecure cookie and a local Redis URL. | `APP_ENV=production` now requires the database URL, `COOKIE_SECURE`, https frontend origins, and a non-local Redis URL. |
| High | The site and API are separate Render services, so a `SameSite=lax` cookie would not be sent. | `render.yaml` sets `COOKIE_SAMESITE=none` with `COOKIE_SECURE=true`. |
| High | No liveness endpoint separate from the database check. | `GET /live` is process-only. `GET /ready` requires PostgreSQL and reports Redis without failing on it. |
| High | No host config for SPA routing, API start, or workers. | `render.yaml` defines the static site, API, and worker. `python -m app.workers.supervisor` runs the loops. |
| High | No CI. | `.github/workflows/ci.yml` runs frontend checks and backend tests against Postgres. It does not deploy. |
| Medium | Unhandled exceptions could surface framework error pages. | Generic JSON error plus `X-Request-ID`. Validation errors still return 422. Production disables `/docs`. |
| Medium | Backtest creation had no per-user rate limit. | `BACKTEST_RUNS_PER_HOUR` (default 20) on `POST /api/backtests/runs`. |
| Medium | Development seed could be run against production and creates a known development account. | Seed exits when `APP_ENV=production`. |
| Medium | No in-app research disclaimer. | Shown on auth cards and in the signed-in navigation. |
| Low | `ComingSoonPage.tsx` is unused and not routed. | Left in the tree. It is not linked. |
| Low | Focus outline was easy to miss. | `:focus-visible` in `index.css`. |

## Checked and left as-is

- Frontend services use `apiRequest` with credentials. No `localStorage` or `sessionStorage` for account data.
- User-owned routes take the user from the session. Cross-user ids return 404 in the existing tests.
- `.env` is gitignored. `.env.example` has names only.
- Redis remains cache and rate-limit storage. PostgreSQL remains the record store.
- Provider failures on quotes, news, and AI already return unavailable states rather than invented content.
- Row Level Security is not the access path. The API uses the database role. The browser has no Supabase key.

## Not done

- No live deploy and no production smoke test.
- Dependency audit was not cleanly available as a failing gate. See the final report for what was run.
- Legal review of the disclaimer was not performed. The copy does not claim regulatory compliance.
