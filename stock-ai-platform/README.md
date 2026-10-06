# StockSense AI

Research and tracking for Indian listed equities (NSE and BSE, INR). Accounts, watchlists, alerts, portfolios, and backtests are stored in PostgreSQL for the signed-in user. Quotes, news, and written analysis appear only when a provider is configured and returns data. Nothing in the product is a forecast, a guarantee, or a personal recommendation.

Deployment files and the release checklist are in `docs/deployment.md` and `docs/release-checklist.md`. The readiness audit is `docs/production-readiness-audit.md`. This repository is not a completed live deployment.

## Layout

```
stock-ai-platform/
├── frontend/     React, TypeScript, Vite, Tailwind CSS
├── backend/      FastAPI application
├── database/     Alembic migrations
├── workers/      Reserved for Redis-backed background jobs
├── docs/         Architecture, database, and API notes
├── docker-compose.yml
└── .env.example
```

See [docs/architecture.md](docs/architecture.md) for how the pieces fit together.

## Prerequisites

- Node.js 20+
- Python 3.11+
- Docker with Docker Compose (Redis)
- A Supabase PostgreSQL project

## Setup

From the `stock-ai-platform` directory:

```bash
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to the Supabase session pooler URI (port 5432) or the direct database URI. Leave it empty in `.env.example`. Do not put that value in frontend environment variables.

Leave `MARKET_DATA_API_KEY` empty. The built-in `yahoo` adapter does not use a key. Quotes are delayed, and fundamental filing dates are not supplied by that feed.

Start Docker Desktop, then Redis:

```bash
docker compose up -d
```

### Backend

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Apply the schema and load fictional development records:

```bash
alembic upgrade head
python -m app.db.seed
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app shell is at [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Current scope

- Project structure, configuration, and placeholders
- `GET /health`
- Account registration, login, logout, profile, and password reset with an HttpOnly session cookie
- Indian stock master (NSE and BSE) and stock search
- Quote and stored OHLCV APIs, plus a close-price and volume chart. The default provider is the Yahoo chart adapter. Quotes are delayed
- Reported fundamentals and point-in-time valuation snapshots from the Yahoo timeseries adapter. Filing dates are not supplied
- Daily technical indicators, chart-pattern detection, support and resistance zones, and an evidence-based conclusion. See `docs/technical-analysis.md`. This is not a forecast or a trade instruction
- Named watchlists stored in PostgreSQL for the signed-in user. A quote is shown only when the market-data service has one, and a delayed quote is labeled delayed
- Metric threshold registry and evaluation for stored fundamental and technical values. See `docs/metrics.md`. A result is not a trade instruction
- User-owned price, fundamental, technical, and chart-pattern alerts, plus in-app notifications and pop-ups. See `docs/alerts.md`. Evaluation is scheduled and is not a real-time guarantee
- Indian market headlines from configured RSS feeds, with lexicon sentiment. See `docs/news.md`. No headlines are shown until a feed is configured
- Stock research that explains stored fundamental, technical, pattern, and news evidence. See `docs/ai.md`. No narrative is shown until `AI_PROVIDER` is configured, and there is no numeric buy or sell score
- Indian share portfolios from the transactions you enter, with weighted-average cost, cash deposits, and a hypothetical position-size calculator. See `docs/portfolio.md`. This does not place trades
- Long-only historical backtests of fixed indicator and reversal rules on stored daily bars. See `docs/backtesting.md`. Results are simulations, not orders or forecasts
- PostgreSQL schema, Alembic migrations, and a fictional development seed
- Provider interfaces. A provider name other than `yahoo` stays unconfigured. News stays unconfigured
- Docker Compose for Redis, including short-lived quote, history, fundamental, and technical caches when Redis is running
- Supabase PostgreSQL through `DATABASE_URL`

Run alert checks with `python -m app.alerts.worker` from `backend`. Run news ingest with `python -m app.news.worker` from `backend`. Finish a queued backtest with `python -m app.backtests.worker` from `backend`. The API also completes a run in the request that starts it. One host process for all three loops is `python -m app.workers.supervisor`.

Do not run `python -m app.db.seed` when `APP_ENV=production`. The seed is for local development and includes a development-only account.

Liveness is `GET /live`. Readiness is `GET /ready` (PostgreSQL required, Redis reported). `GET /health` checks PostgreSQL only.

Production (`APP_ENV=production`) requires `DATABASE_URL`, `COOKIE_SECURE=true`, an `https` `FRONTEND_URL`, and a `REDIS_URL` that is not a local hostname. When the site and the API are on different hosts, set `COOKIE_SAMESITE=none` as well. Optional market, news, email, and AI settings may stay empty; those features then show an unavailable or configuration-required state.

```bash
# API, from backend. Render sets PORT.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend production build, from `frontend`:

```bash
npm run build
```

Render hosts the static site, the API, and the worker. See `render.yaml`. Set `VITE_API_BASE_URL` to the public API origin when the site is built. It must not contain secrets.
