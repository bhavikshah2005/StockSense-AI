"""Checks applied after a provider response has been normalized."""

from decimal import Decimal

from app.data_providers.market_data.base import (
    MARKET_SESSION_STATES,
    STORAGE_INTERVALS,
    InstrumentRef,
    MarketStatus,
    PriceBar,
    Quote,
)
from app.data_providers.market_data.errors import MALFORMED, MarketDataError


def validate_quote(quote: Quote, instrument: InstrumentRef) -> Quote:
    if quote.symbol != instrument.symbol or quote.exchange != instrument.exchange:
        raise MarketDataError(MALFORMED)
    if quote.currency != instrument.currency:
        raise MarketDataError(MALFORMED)
    _non_negative(quote.current_price)
    _optional_non_negative(quote.previous_close)
    _optional_non_negative(quote.open)
    _optional_non_negative(quote.high)
    _optional_non_negative(quote.low)
    _high_low(quote.high, quote.low)
    _inside_range(quote.current_price, quote.low, quote.high)
    _inside_range(quote.open, quote.low, quote.high)
    if quote.volume is not None and quote.volume < 0:
        raise MarketDataError(MALFORMED)
    _aware(quote.market_timestamp)
    if quote.delay_minutes is not None and quote.delay_minutes < 0:
        raise MarketDataError(MALFORMED)
    if quote.delayed and quote.delay_minutes == 0:
        raise MarketDataError(MALFORMED)
    return _with_change(quote)


def validate_bar(bar: PriceBar, interval: str) -> None:
    if bar.interval != interval or interval not in STORAGE_INTERVALS:
        raise MarketDataError(MALFORMED)
    _non_negative(bar.open)
    _non_negative(bar.high)
    _non_negative(bar.low)
    _non_negative(bar.close)
    _optional_non_negative(bar.adjusted_close)
    _high_low(bar.high, bar.low)
    _inside_range(bar.open, bar.low, bar.high)
    _inside_range(bar.close, bar.low, bar.high)
    if bar.volume < 0:
        raise MarketDataError(MALFORMED)
    _aware(bar.timestamp)


def validate_status(status: MarketStatus, exchange: str) -> None:
    if status.exchange != exchange or status.status not in MARKET_SESSION_STATES:
        raise MarketDataError(MALFORMED)
    if not status.source.strip():
        raise MarketDataError(MALFORMED)
    _aware(status.observed_at)


def _with_change(quote: Quote) -> Quote:
    change = quote.change
    percent = quote.change_percent
    if change is None and quote.previous_close is not None:
        change = (quote.current_price - quote.previous_close).quantize(Decimal("0.0001"))
    if (
        percent is None
        and change is not None
        and quote.previous_close is not None
        and quote.previous_close != 0
    ):
        percent = ((change / quote.previous_close) * Decimal(100)).quantize(Decimal("0.0001"))
    if change is not None:
        change = change.quantize(Decimal("0.0001"))
    if percent is not None:
        percent = percent.quantize(Decimal("0.0001"))
    return Quote(
        symbol=quote.symbol,
        exchange=quote.exchange,
        currency=quote.currency,
        current_price=quote.current_price,
        previous_close=quote.previous_close,
        change=change,
        change_percent=percent,
        open=quote.open,
        high=quote.high,
        low=quote.low,
        volume=quote.volume,
        market_timestamp=quote.market_timestamp,
        delayed=quote.delayed,
        delay_minutes=quote.delay_minutes,
    )


def _non_negative(value: Decimal) -> None:
    if value < 0:
        raise MarketDataError(MALFORMED)


def _optional_non_negative(value: Decimal | None) -> None:
    if value is not None and value < 0:
        raise MarketDataError(MALFORMED)


def _high_low(high: Decimal | None, low: Decimal | None) -> None:
    if high is not None and low is not None and high < low:
        raise MarketDataError(MALFORMED)


def _inside_range(value: Decimal | None, low: Decimal | None, high: Decimal | None) -> None:
    if value is None or low is None or high is None:
        return
    if value < low or value > high:
        raise MarketDataError(MALFORMED)


def _aware(value: object) -> None:
    tzinfo = getattr(value, "tzinfo", None)
    if tzinfo is None or tzinfo.utcoffset(value) is None:
        raise MarketDataError(MALFORMED)
