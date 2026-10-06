# Technical analysis

Daily technical readings are calculated from stored `stock_prices.close`. Adjusted close is not used, because it is often missing. The service does not invent bars for missing sessions. Pattern coordinates come from the pivot rules below, not from a language model.

These readings describe historical prices. They are not forecasts, probabilities, or trade instructions.

## Indicators (`indicators-1`)

| Reading | Rule |
| --- | --- |
| SMA 20 / 50 / 100 / 200 | Mean of that many closes. Null until the window is full. |
| EMA 20 / 50 | Seeded with the SMA of the first window, then weighted with `2 / (period + 1)`. |
| RSI 14 | Wilder smoothing. Null when the average gain and average loss are both zero. 100 when the average loss is zero and the average gain is positive. |
| MACD | EMA 12 minus EMA 26. Signal is the EMA 9 of the MACD values. Histogram is MACD minus signal. |
| Average volume | Mean of the last 20 volumes. |
| Historical volatility | Sample standard deviation of the last 20 log returns, times the square root of the annualization factor, times 100. The result is an annualized percent. Daily bars use 252. This is not implied volatility. |
| 52-week high and low | Maximum high and minimum low of the last 252 sessions. Null before that. Distance is the latest close versus that extreme, in percent. |
| Performance | Percent change from the close `N` sessions back: 1, 5, 21, 63, 126, and 252. These are sessions, not calendar days. |

The latest indicator row is stored on `technical_indicators` for the last bar, the interval, and `indicators-1`. The chart series is calculated from `stock_prices` for the request.

## Pivots (`pivots-1`)

A swing high at bar `i` requires the high to be strictly above the highs of the 5 bars on each side. A swing low uses the same window on lows. The pivot can be used only after the later bar exists. Its `confirmed_at` timestamp is that later bar, so a reading cannot treat the pivot as known on the bar where the extreme printed.

Equal neighboring highs or lows do not create a pivot. That keeps flat stretches from producing a pivot on every bar. Gaps stay empty. No bar is inserted to fill them.

## Pattern status

| Status | Meaning |
| --- | --- |
| `developing` | The structure matches and the confirmation close has not happened. |
| `confirmed` | A completed candle closed beyond the boundary by the buffer. |
| `completed` | At least three closes stayed beyond the boundary. This is a retrospective observation, not a claim that the move succeeded. |
| `invalidated` | Before confirmation, a close beyond the pattern's invalidation price. After three confirming closes, a later close back through the boundary. |
| `insufficient_data` | Not enough bars. The API reports this on the conclusion instead of inventing a pattern. |

A developing formation is never labeled confirmed.

The breakout buffer is the larger of 0.5 percent of price and 0.25 times the 14-session average true range. Volume is reported as above or not above the prior 20-session average when those volumes exist. Missing volume is called unavailable. Volume does not by itself confirm a cross.

## Detectors (`patterns-1`)

Each detector returns at most the latest structure that meets its rules. A near miss returns nothing.

- Head and shoulders / inverse: three extremes, the middle one beyond the other two by at least 1 percent, shoulders within 15 percent of each other, and a neckline pivot between each pair. Spacing is at least 5 bars.
- Double and triple tops / bottoms: repeated extremes within 3 percent, with at least a 3 percent retracement between them. The neckline is the intervening extreme. Confirmation is a close beyond that neckline.
- Triangles, wedges, and rectangles: at least two swing highs and two swing lows. Boundaries are least-squares lines. A slope is flat when it is under 0.15 percent of price per bar. A rectangle also needs a width of 2 to 20 percent and a stable gap. Triangles and wedges must narrow. The fit is not extended past the last pivot.
- Bull and bear flags: a prior move of at least 10 percent over 3 to 40 bars, then a consolidation whose height is at most half of that move. The prior move is not a target.
- Swing structure: the latest two confirmed highs and lows. Higher highs and higher lows, or lower highs and lower lows. This stays `developing` because it is a description, not a breakout.

If none of these rules match, the conclusion says no reliable chart pattern was detected.

## Support and resistance

Confirmed swing highs are clustered into resistance and swing lows into support when prices sit within 1.5 percent of the cluster average. A zone needs two reactions before the API returns it. One isolated touch is not described as a repeated reaction. `active` means the latest close is still on the zone's near side. `breached` means it has closed through the zone. The zone width is the span of the clustered pivots.

## Conclusion rubric

The category is not a score.

- `insufficient_data`: fewer than 60 bars.
- `bullish_evidence`: at least one of rising swings, a close above both the 20- and 50-session averages, RSI at or above 60, a positive MACD histogram, or a confirmed bullish structure. No bearish item from the mirror list.
- `bearish_evidence`: the mirror, with RSI at or below 40.
- `mixed_evidence`: both sides have an item.
- `no_clear_direction`: neither side has an item.

A developing pattern is described in the text and does not set the category by itself. RSI and MACD disagreement is stated as a conflict. The text always says the reading is not a forecast and not a trade instruction.

## API

Authenticated:

- `GET /api/stocks/{stock_id}/technical-analysis?interval=1d&start_date=&end_date=`
- `GET /api/stocks/{stock_id}/technical-analysis/patterns`
- `GET /api/stocks/{stock_id}/technical-analysis/summary`

Only `1d` is accepted. The default window is 800 calendar days and the maximum is 1100. Pattern history limit is 1 to 50. Responses are cached with the history TTL. The cache key includes the stock, interval, dates, detector version, indicator version, and the last stored bar time, so a new bar or a version change misses the cache.

A listing with no stored bars and no configured provider returns 503. Stored bars are still analyzed when a later provider call fails.

## Adding a detector

1. Add a module under `backend/app/analysis/patterns/` that returns `PatternHit` values.
2. Call it from `analyze` in `engine.py`.
3. Add a definition string in `technical_service.py`.
4. Add a synthetic positive case and a near-miss case in `tests/test_technical_analysis.py`.
5. Raise `DETECTOR_VERSION` in `config.py` when the rules change so stored rows stay tied to the method that produced them.

Do not fill a failed detection with a guessed pattern.
