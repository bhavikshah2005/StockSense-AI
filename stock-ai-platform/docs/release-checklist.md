# Release checklist

Do not treat a green local build as a live deployment. Complete the external host setup, then smoke-test the deployed origins.

## Before deployment

- [ ] Read `docs/production-readiness-audit.md` and confirm no release-blocking item is still open.
- [ ] `APP_ENV=production` is set only on the hosts, with `COOKIE_SECURE=true` and an `https` `FRONTEND_URL`.
- [ ] `DATABASE_URL` is the Supabase session pooler. The password is not in git.
- [ ] `REDIS_URL` is the managed `rediss://` URL, not localhost.
- [ ] `VITE_API_BASE_URL` is the public API origin and contains no secret.
- [ ] `COOKIE_SAMESITE=none`, because the Render site and API are separate services.
- [ ] Optional AI, news, and email variables are set only for features that should be live.
- [ ] A Supabase backup or snapshot exists.
- [ ] `alembic upgrade head` has been reviewed and applied to the target database.
- [ ] `python -m app.db.seed` was not run against production.

## Deploy

- [ ] Frontend: Render static site `stocksense-web` from `render.yaml`, with `VITE_API_BASE_URL` set to the API origin.
- [ ] API: Render web service `stocksense-api` from `render.yaml`, health check `/live`.
- [ ] Worker: Render worker `stocksense-workers`, command `python -m app.workers.supervisor`.
- [ ] `FORWARDED_ALLOW_IPS=*` is set only for the Render proxy.

## Smoke test

- [ ] `GET /live` returns `{"status":"ok"}`.
- [ ] `GET /ready` returns database `ok`. Redis may be `unavailable` only during a cache outage.
- [ ] Register or sign in on the production site, refresh, and stay signed in.
- [ ] Sign out. A protected API call returns 401.
- [ ] Stock search opens a real listing or a clear empty/unavailable state.
- [ ] News and AI match their configuration. They do not show sample articles or sample analysis.
- [ ] A portfolio or backtest page loads for the signed-in user and does not show another user's data.

## After release

- [ ] Watch API errors, `/ready`, and worker logs for the first hour.
- [ ] Confirm request logs contain a request id and do not contain passwords, cookies, or provider keys.

## Rollback

- [ ] Redeploy the previous API and frontend builds if the release is bad and the database schema did not change.
- [ ] If a migration was applied, prefer a forward fix. Run `downgrade` only when that migration's downgrade is known to keep user data.
- [ ] Restore the Supabase snapshot if user data was damaged. That is a manual Supabase action.
