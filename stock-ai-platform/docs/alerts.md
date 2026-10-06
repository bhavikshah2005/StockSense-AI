# Alerts and notifications

Alerts belong to the signed-in user and are stored in PostgreSQL. Evaluation reads stored prices, fundamentals, valuations, technical indicators, and chart-pattern rows. It uses the same comparison functions as the metric threshold engine. It does not call Yahoo, invent a missing value, or create a trade instruction.

Delivery is not real-time. The worker checks active alerts on `ALERT_EVAL_INTERVAL_SECONDS` (default 300, allowed 30–3600). A provider delay, a closed market, or a missed worker run can delay a trigger.

## Supported conditions

| Category | What it checks | Required stored data |
| --- | --- | --- |
| Price | Latest daily close above, below, or crossing a value in INR | At least one daily close. A cross also needs the previous daily close. |
| Price change | Percent move over 1, 5, or 20 stored sessions | Enough daily closes for that interval. `>` means a rise of at least that percent. `<` means a fall of at least that percent. |
| Fundamental | A registry metric against an absolute bound, or against the threshold engine when the basis is sector-relative | The same reading the metrics page uses. A missing or stale report stays unmet. |
| Technical | A registry indicator or event, including RSI levels and crossovers the registry already supports | Stored indicator history. A cross without a previous reading is not a trigger. |
| Pattern | Latest daily pattern of a supported type is `confirmed`, `invalidated`, or `completed` | A `technical_patterns` row from the existing detector. Developing, uncertain, and insufficient states cannot be targets. |

`GET /api/alerts/catalog` is the list the form uses. A metric or pattern that is not in that catalog is rejected.

## Lifecycle

`active` is evaluated. `paused` is not. `triggered` means a once-only alert already fired and will not fire again until it is resumed. `disabled` is reserved for an alert the system will not run. `is_active` is true only while the status is `active`.

`repeat_mode` is `once` or `repeat`.

A level or cross fires only when the alert is armed and the current comparison is `met`. After it fires, it is disarmed. A once-only alert then becomes `triggered`. A repeating alert stays `active` and stays quiet while the condition remains true. It arms again, and its generation increases, only when a later check is `not_met`. A pattern arms again when the stored status leaves the target status. The same stored pattern row and status is not written twice for one generation.

Editing the condition of an active alert arms it again and increases the generation. Trigger history is kept. Resume from `paused` or `triggered` also arms the alert and increases the generation.

Missing data, stale data, an unavailable sector context, and a missing threshold record `last_data_status` and do not create an event. The worker does not decide that the market is open from the server clock. It compares the timestamps already stored with the data.

## Duplicate prevention

Each event has an idempotency key of alert id, arm generation, observation timestamp, and pattern id. The unique index `uq_alert_events_idempotency` rejects a retry that would insert the same event. The insert uses a nested transaction, so a duplicate key does not undo the rest of the evaluation. `evaluate_active` takes PostgreSQL advisory lock `81411011` so two workers do not evaluate the same pass together. Redis is not the record of alerts or events.

## Notifications

An in-app notification points at one trigger event. Marking it read sets `notifications.read_at` and leaves `alert_events` in place. A notification is created when the user has no preference row or `in_app_enabled` is true. While the app is open, the newest unread notification also appears as a pop-up. Dismissing it marks that notification read.

Alerts are delivered in the app only. There is no email, SMS, WhatsApp, or push channel.

## Worker

From `backend`, with `DATABASE_URL` set and any shell override of that variable removed:

```bash
python -m app.alerts.worker
```

The process loops, evaluates active alerts, and sleeps for `ALERT_EVAL_INTERVAL_SECONDS`. Run one copy in production. The advisory lock skips a second copy that starts during a pass. The worker does not download market data. Refresh prices and indicators with the existing stock services first.

`ALERT_MAX_PER_USER` defaults to 50 and must be from 1 to 200.

## Checks

```bash
alembic upgrade head
pytest tests/test_alerts.py
```

Frontend:

```bash
npx vitest run tests/AlertsPage.test.tsx --pool=threads
```
