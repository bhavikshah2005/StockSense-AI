"""Calendar windows for chart ranges. Dates are Asia/Kolkata civil dates."""

from calendar import monthrange
from datetime import date, timedelta

from app.data_providers.market_data.base import INTRADAY_INTERVALS, STORAGE_INTERVALS
from app.data_providers.market_data.errors import INVALID_QUERY, UNSUPPORTED_INTERVAL, MarketDataError

CHART_RANGES: tuple[str, ...] = ("1d", "1w", "1m", "3m", "6m", "1y", "3y", "5y", "max")
INTRADAY_MAX_DAYS = 10
# A hole longer than a long weekend is treated as missing data.
GAP_DAYS = 6
# Do not refetch a daily tail that is only a weekend or a short holiday behind.
TAIL_SLACK_DAYS = 4
MAX_BARS = 3000


def resolve_window(
    *,
    range_name: str | None,
    start: date | None,
    end: date | None,
    today: date,
    max_years: int,
) -> tuple[date, date, str | None]:
    has_range = bool(range_name)
    has_dates = start is not None or end is not None
    if has_range == has_dates:
        raise MarketDataError(INVALID_QUERY)
    if has_range:
        assert range_name is not None
        normalized = range_name.strip().lower()
        if normalized not in CHART_RANGES:
            raise MarketDataError(INVALID_QUERY)
        return _range_start(today, normalized, max_years), today, normalized
    if start is None or end is None or start > end:
        raise MarketDataError(INVALID_QUERY)
    if (end - start).days > max_years * 366:
        raise MarketDataError(INVALID_QUERY)
    return start, end, None


def choose_interval(
    *,
    range_name: str | None,
    requested: str | None,
    supported: frozenset[str],
) -> str:
    if requested:
        if requested not in STORAGE_INTERVALS:
            raise MarketDataError(UNSUPPORTED_INTERVAL)
        return requested
    if range_name == "1d":
        for candidate in ("5m", "15m", "1h"):
            if candidate in supported:
                return candidate
    return "1d"


def limit_intraday(interval: str, start: date, end: date) -> None:
    if interval in INTRADAY_INTERVALS and (end - start).days > INTRADAY_MAX_DAYS:
        raise MarketDataError(INVALID_QUERY)


def missing_spans(bar_days: list[date], start: date, end: date) -> list[tuple[date, date]]:
    """Head, interior, and tail gaps. Weekend holes are left alone."""
    if not bar_days:
        return [(start, end)]
    ordered = sorted(set(bar_days))
    spans: list[tuple[date, date]] = []
    if (ordered[0] - start).days > GAP_DAYS:
        spans.append((start, ordered[0] - timedelta(days=1)))
    for previous, nxt in zip(ordered, ordered[1:], strict=False):
        if (nxt - previous).days > GAP_DAYS:
            spans.append((previous + timedelta(days=1), nxt - timedelta(days=1)))
    if (end - ordered[-1]).days > TAIL_SLACK_DAYS:
        tail_start = ordered[-1] + timedelta(days=1)
        if tail_start <= end:
            spans.append((tail_start, end))
    return [(span_start, span_end) for span_start, span_end in spans if span_start <= span_end]


def _range_start(today: date, range_name: str, max_years: int) -> date:
    if range_name == "1d":
        return today
    if range_name == "1w":
        return today - timedelta(days=7)
    if range_name == "1m":
        return _shift_months(today, 1)
    if range_name == "3m":
        return _shift_months(today, 3)
    if range_name == "6m":
        return _shift_months(today, 6)
    if range_name == "1y":
        return _shift_years(today, 1)
    if range_name == "3y":
        return _shift_years(today, 3)
    if range_name == "5y":
        return _shift_years(today, 5)
    return _shift_years(today, max_years)


def _shift_months(day: date, months: int) -> date:
    month = day.month - months
    year = day.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def _shift_years(day: date, years: int) -> date:
    year = day.year - years
    return date(year, day.month, min(day.day, monthrange(year, day.month)[1]))
