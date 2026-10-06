"""Deterministic range statistics from stored bars."""

from decimal import Decimal

from app.models import StockPrice


def performance_and_extremes(
    bars: list[StockPrice],
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal] | None:
    """Return start, end, change, change percent, period high, and period low."""
    if not bars:
        return None
    start_price = _money(bars[0].close)
    end_price = _money(bars[-1].close)
    change = _money(end_price - start_price)
    if start_price == 0:
        percent = Decimal("0.0000")
    else:
        percent = _money((change / start_price) * Decimal(100))
    period_high = _money(max(bar.high for bar in bars))
    period_low = _money(min(bar.low for bar in bars))
    return start_price, end_price, change, percent, period_high, period_low


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
