# Metric thresholds

The threshold engine compares a stored metric with one resolved rule. It does not create alerts, send messages, or recommend a trade.

## Registry

Definitions live in `backend/app/metrics/registry.py`. The schema version is `metrics-1`.

To add a metric, add a `MetricDefinition` whose `key` matches a value the readers already load:

- `valuation` and `fundamental` keys are columns on the latest stored snapshot or report.
- `derived_fundamental` keys call `cfo_to_net_profit` and `annual_cagr`.
- `technical` keys are columns on the latest stored daily indicator row.
- `technical_pair` keys compare two columns on the previous and current indicator rows.
- `price` and `derived_technical` use the latest daily close together with the stored 52-week bounds.

Set `operators`, `sector_benchmark` only when `sector_benchmarks` has that column, and `event_kind` of `level` or `pair` for crossings. Do not register a metric the database cannot supply.

## Conditions

`operator` is one of `>`, `>=`, `<`, `<=`, `between`, `outside_range`, `crosses_above`, or `crosses_below`.

- A level condition stores `threshold_value`. A range also stores `threshold_high`, and the high bound must be greater.
- `basis = sector_benchmark` compares the stock value with the latest sector benchmark and stores no numeric bound.
- A level crossing compares the previous and current readings with `threshold_value`. One reading is `insufficient_data`.
- A pair crossing, such as SMA 20 through SMA 50, uses the previous and current pairs and stores no numeric bound.

Definition rows use version `thresholds-1`.

## Precedence

For one stock and metric, on the evaluation date:

1. The user's active threshold for that stock.
2. The user's active threshold with no stock.
3. An active sector threshold whose sector matches and whose country matches or is empty.
4. An active country threshold for the stock's country. India uses `IN`.
5. An active platform (`global`) threshold.

A row is skipped when `is_active` is false or the evaluation date is outside `effective_from` / `effective_to`. If several rows share a scope, the newest `updated_at` is used. New writes reject a second active row for the same metric, scope, sector, country, user, and stock.

The response names the chosen scope, the higher scopes that did not match, and whether it is a user override.

## Freshness

Evaluation does not call Yahoo. A missing stored value is `insufficient_data`. Fundamental and valuation freshness reuse `FUNDAMENTAL_REPORT_STALE_HOURS` and `FUNDAMENTAL_VALUATION_STALE_HOURS`. Indicator and price freshness uses the same seven-day window as technical analysis. Stale values return `stale_data` and are not marked met. A missing sector benchmark returns `context_unavailable`.

## Commands

```bash
cd backend
alembic upgrade head
python -m pytest tests/test_threshold_engine.py tests/test_threshold_api.py
```

`THRESHOLD_MAX_USER_OVERRIDES` defaults to 100.
