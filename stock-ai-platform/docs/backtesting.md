# Backtesting

Historical evaluation for one NSE or BSE listing. The signed-in user owns each run. The React app calls `/api/backtests`. It does not read the database directly, and it does not keep runs in browser storage.

This module does not place orders, connect to a broker, or describe a result as a forecast.

## Strategies

The registry is fixed. Version `1` of each key is the only accepted version. Users send a parameter object. They cannot upload code.

| Key | Rule |
| --- | --- |
| `sma_crossover` | Enter when the short simple average finishes above the long average after finishing at or below it. Exit on the opposite cross. Periods default to 20 and 50. The short period must be lower. |
| `rsi_cross` | Enter when RSI crosses up through the entry level. Exit when it crosses down through the higher exit level. Defaults are 14, 30, and 70. Uses `app.analysis.indicators.rsi`. |
| `macd_cross` | Enter when the MACD line crosses above its signal line. Exit on the opposite cross. Periods stay 12, 26, and 9 from `macd()`. |
| `sma_rsi` | Enter only when the short average is above the long average and RSI crosses up through the entry level on the same completed session. Exit when the short average is no longer above, or RSI crosses down through the exit level. |
| `bullish_reversal` | Enter when the existing reversal detector reports a confirmed or completed bullish structure (inverse head and shoulders, double bottom, or triple bottom). The signal bar is the later of the confirming close and the last pivot `confirmed_index`. Earlier points in the formation are not entries. There is no opposite-pattern exit. |

All five are long only and may hold overnight. A session with a missing indicator value produces no signal. If an entry and an exit are both true while a position is open, the exit is used. If the book is flat, the entry is used.

Indicator values at bar `i` are computed from closes through `i` only, using the same functions as the technical-analysis page.

## Data

Runs read stored `stock_prices` rows with `interval = 1d`. They do not call the quote endpoint, and they do not download missing history during the run. Load history from the stock page first. If the stored bars do not reach the requested start or end (more than 10 calendar days short), or there are not enough sessions before the start to warm up the indicator, the status is `insufficient_data`. The requested period is not shortened.

Bars are ordered by timestamp. Invalid OHLC and duplicate timestamps follow `prepare_bars`: invalid rows are dropped, and a duplicate timestamp keeps the last row. A weekday gap longer than 10 calendar days is reported and left empty. No candle, volume, or price is invented.

The fill price is the raw open or raw close. `adjusted_close` is not applied, including when it is present. Splits, dividends, and other corporate actions can change the result. The stock master is the current listing universe, so delisted names are absent. A one-stock run does not model historical universe selection. Present-day sector labels are not used as if they were known in the past.

There is no stored index series, so benchmark comparison is omitted and the summary says why.

## Execution

Engine version `backtest-1`. Sizing version `simulation-cash-1`. This sizing spends available simulated cash on whole shares. It is not the portfolio position-size calculator.

- Initial capital is 1,000 to 100,000,000 INR.
- One long position at a time. No short, margin, or leverage.
- A signal on a completed session fills at the next stored session's open.
- The final open position, if any, is closed at the last completed close because no following session exists. The reason is `end_of_test`.
- A signal on the final session is not filled.
- Buy slippage raises the open. Sell slippage lowers the exit price. Both are basis points from 0 to 100.
- Brokerage is a percent of notional from 0 to 5, charged on entry and exit. Shares are reduced until notional plus charges fit in cash.
- Brokerage and slippage of zero are allowed only as explicit inputs. Those runs are labeled `gross`. Any positive cost is labeled `net`.
- Optional stop and take-profit are percents from the simulated entry price. A gap through the stop fills at the open when that open is worse than the stop.
- If one candle's low reaches the stop and its high reaches the target, the exit is the stop (`ambiguous_stop_and_target`). The target is not chosen.
- Optional max holding length exits at the next session open (`max_hold`).
- A stop fill is not a promise that a live order would have traded there.

## Metrics

Figures come from the simulated trades and the close-to-close equity series. Money is rounded half up to paise. Ratios use six decimal places.

- Total return is final equity minus initial equity. The percent divides by initial equity. Initial equity is always positive.
- Annualized return is `(final / initial) ^ (252 / sessions) - 1`, only when there are at least 252 sessions and ending equity is positive. Otherwise it is unavailable.
- Maximum drawdown is the largest peak-to-trough decline divided by the peak. Duration is the session count from that peak until equity recovers or the series ends.
- Win rate is winning trades divided by completed trades. With no trades it is unavailable.
- Profit factor is gross winning P&L divided by the absolute gross losing P&L. With no losing trades it is unavailable, not infinite.
- Exposure is the share of sessions with a position. Turnover is traded notional divided by average equity when that average is positive.
- Transaction costs are brokerage plus the rupee value of slippage.

Sharpe and similar ratios are not shown. No risk-free series is stored.

## API

All routes require the session cookie. Another user's run returns 404.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/backtests/strategies` | Registry and parameter bounds. |
| POST | `/api/backtests/runs` | Validate, store, and finish one run. |
| GET | `/api/backtests/runs?limit=&offset=` | The caller's runs. Limit 1–50. |
| GET | `/api/backtests/runs/{id}` | Summary, warnings, and status. |
| GET | `/api/backtests/runs/{id}/trades` | Simulated trades. |
| GET | `/api/backtests/runs/{id}/equity` | Equity and drawdown points. |
| DELETE | `/api/backtests/runs/{id}` | Delete a finished run. |
| GET | `/api/backtests/compare?left=&right=` | Show two owned runs together. Overlapping runs with the same stock, strategy, and assumptions can be compared. The note is not a ranking. |

Example create body:

```json
{
  "stock_id": "10c53c6a-609d-4663-b02f-71d741b22439",
  "strategy_key": "sma_crossover",
  "strategy_version": "1",
  "parameters": {"short_period": 20, "long_period": 50},
  "start_date": "2024-01-02",
  "end_date": "2024-12-31",
  "initial_capital": "100000.00",
  "brokerage_percent": "0.10",
  "slippage_bps": "5",
  "position_percent": "100"
}
```

A finished body includes `status` (`completed`, `partial`, or `insufficient_data`), `summary`, and `warnings`. Invalid input returns 422. A second run while one is `queued` or `running` returns 409. At most `BACKTEST_MAX_RUNS` (default 30) are kept. The date span cannot exceed `BACKTEST_MAX_CALENDAR_DAYS` (default 1098) and cannot end after today.

`partial` means at least one stored bar was dropped as invalid or duplicate and the remaining coverage was still enough to run.

Statuses `queued` and `running` exist so a worker can finish a run that was left queued. The API request completes the run before it responds. A run is not `completed` until trades, equity points, and the summary are committed.

## Worker and tests

From `backend`, after `alembic upgrade head`:

```bash
python -m app.backtests.worker
```

The interval is `BACKTEST_WORKER_INTERVAL_SECONDS` (default 30, range 5–300). Postgres advisory lock `81411015` stops two workers from claiming the same pass. A `running` row older than 15 minutes is queued again. A second claim of a finished run does not insert another trade set.

```bash
pytest tests/test_backtests.py
```

Tests use fixture bars. They do not call a paid provider.

## Limits

No options, futures, shorts, margin, intraday order book, or automated trading. No new model narrative. Pattern entries depend on walking the existing detector without future bars; the detector still keeps only the latest structure inside each prefix, so earlier discarded structures are not replayed. Corporate actions and delistings are disclosed gaps, not filled.
