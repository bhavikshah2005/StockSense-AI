"""Yahoo Finance chart adapter for NSE and BSE quotes, bars, and session state.

Daily and intraday bars come from `/v8/finance/chart`. Prices are the vendor's
regular-session values in INR. The feed does not publish an exact delay, so
quotes are marked delayed without a guessed minute count.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.data_providers.market_data.base import (
    STORAGE_INTERVALS,
    InstrumentRef,
    MarketDataProvider,
    MarketStatus,
    PriceBar,
    Quote,
)
from app.data_providers.market_data.errors import MarketDataError
from app.data_providers.market_data.normalize import normalize_bar, normalize_quote
from app.data_providers.yahoo.http import DEFAULT_BASE_URL, YahooClient, YahooStatus
from app.data_providers.yahoo.parse import as_decimal, as_int, unix_time, yahoo_symbol
from app.markets.profile import active_market
from app.markets.time import IST

_YAHOO_INTERVAL = {"1d": "1d", "1h": "60m", "15m": "15m", "5m": "5m"}


class YahooMarketDataProvider(MarketDataProvider):
    def __init__(self, client: YahooClient | None = None) -> None:
        configured = get_settings().market_data_base_url.strip()
        self._client = client or YahooClient(configured or DEFAULT_BASE_URL)

    @property
    def name(self) -> str:
        return "yahoo"

    @property
    def supported_intervals(self) -> frozenset[str]:
        return STORAGE_INTERVALS

    def get_quote(self, instrument: InstrumentRef) -> Quote:
        self._reject(instrument.exchange, instrument.currency, instrument.country)
        chart = self._chart(instrument, interval="1d", start=None, end=None, range_name="5d")
        meta = _meta(chart)
        price = as_decimal(meta.get("regularMarketPrice"))
        if price is None:
            raise MarketDataError("not_found")
        high = as_decimal(meta.get("regularMarketDayHigh"))
        low = as_decimal(meta.get("regularMarketDayLow"))
        opened = as_decimal(meta.get("regularMarketOpen"))
        if opened is None:
            opened = as_decimal(_last_bar_field(chart, "open"))
        if high is None or low is None or price < low or price > high:
            high = None
            low = None
            opened = None
        elif opened is not None and (opened < low or opened > high):
            opened = None
        volume = as_int(meta.get("regularMarketVolume"))
        return normalize_quote(
            {
                "symbol": instrument.symbol,
                "exchange": instrument.exchange,
                "currency": instrument.currency,
                "current_price": format(price, "f"),
                "previous_close": _text(as_decimal(meta.get("chartPreviousClose") or meta.get("previousClose"))),
                "change": None,
                "change_percent": None,
                "open": _text(opened),
                "high": _text(high),
                "low": _text(low),
                "volume": volume,
                "market_timestamp": unix_time(meta.get("regularMarketTime")),
                "delayed": True,
                "delay_minutes": None,
            },
            instrument,
        )

    def get_historical_prices(
        self,
        instrument: InstrumentRef,
        *,
        start: date,
        end: date,
        interval: str,
    ) -> list[PriceBar]:
        self._reject(instrument.exchange, instrument.currency, instrument.country)
        if interval not in _YAHOO_INTERVAL:
            raise MarketDataError("unsupported_interval")
        chart = self._chart(instrument, interval=interval, start=start, end=end, range_name=None)
        return _bars(chart, interval, start, end)

    def get_market_status(self, exchange: str) -> MarketStatus:
        self._reject_exchange(exchange)
        reference = "^NSEI" if exchange == "NSE" else "^BSESN"
        try:
            payload = self._client.get_json(
                f"/v8/finance/chart/{reference}",
                {"interval": "1d", "range": "1d", "includeAdjustedClose": "true"},
            )
        except YahooStatus as exc:
            raise MarketDataError(_market_code(exc.code)) from None
        chart = payload.get("chart")
        if not isinstance(chart, dict) or not isinstance(chart.get("result"), list) or not chart["result"]:
            raise MarketDataError("unavailable")
        result = chart["result"][0]
        if not isinstance(result, dict):
            raise MarketDataError("unavailable")
        return _status(exchange, _meta(result))

    def _chart(
        self,
        instrument: InstrumentRef,
        *,
        interval: str,
        start: date | None,
        end: date | None,
        range_name: str | None,
    ) -> dict[str, Any]:
        params = {"interval": _YAHOO_INTERVAL[interval], "includeAdjustedClose": "true"}
        if range_name is not None:
            params["range"] = range_name
        else:
            assert start is not None and end is not None
            params["period1"] = str(int(datetime.combine(start, datetime.min.time(), tzinfo=IST).timestamp()))
            params["period2"] = str(int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=IST).timestamp()))
        try:
            payload = self._client.get_json(f"/v8/finance/chart/{yahoo_symbol(instrument.symbol, instrument.exchange)}", params)
        except YahooStatus as exc:
            raise MarketDataError(_market_code(exc.code)) from None
        chart = payload.get("chart")
        if not isinstance(chart, dict):
            raise MarketDataError("malformed")
        error = chart.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else None
            raise MarketDataError("not_found" if code == "Not Found" else "unavailable")
        result = chart.get("result")
        if not isinstance(result, list) or not result or not isinstance(result[0], dict):
            raise MarketDataError("not_found")
        return result[0]

    def _reject(self, exchange: str, currency: str, country: str) -> None:
        profile = active_market()
        if exchange not in profile.exchanges or currency != profile.currency or country != profile.country:
            raise MarketDataError("unsupported_exchange")

    def _reject_exchange(self, exchange: str) -> None:
        if exchange not in active_market().exchanges:
            raise MarketDataError("unsupported_exchange")


def _meta(chart: dict[str, Any]) -> dict[str, Any]:
    meta = chart.get("meta")
    if not isinstance(meta, dict):
        raise MarketDataError("malformed")
    return meta


def _bars(chart: dict[str, Any], interval: str, start: date, end: date) -> list[PriceBar]:
    stamps = chart.get("timestamp")
    indicators = chart.get("indicators")
    if not isinstance(stamps, list) or not isinstance(indicators, dict):
        return []
    quote_rows = indicators.get("quote")
    if not isinstance(quote_rows, list) or not quote_rows or not isinstance(quote_rows[0], dict):
        return []
    quote = quote_rows[0]
    adjusted_rows = indicators.get("adjclose")
    adjusted = adjusted_rows[0].get("adjclose") if isinstance(adjusted_rows, list) and adjusted_rows and isinstance(adjusted_rows[0], dict) else None
    bars: list[PriceBar] = []
    for index, stamp in enumerate(stamps):
        opened = as_decimal(_at(quote.get("open"), index))
        high = as_decimal(_at(quote.get("high"), index))
        low = as_decimal(_at(quote.get("low"), index))
        close = as_decimal(_at(quote.get("close"), index))
        volume = as_int(_at(quote.get("volume"), index))
        if None in {opened, high, low, close, volume}:
            continue
        moment = unix_time(stamp)
        day = moment.astimezone(IST).date()
        if day < start or day > end:
            continue
        bars.append(
            normalize_bar(
                {
                    "timestamp": moment,
                    "interval": interval,
                    "open": format(opened, "f"),
                    "high": format(high, "f"),
                    "low": format(low, "f"),
                    "close": format(close, "f"),
                    "adjusted_close": _text(_at(adjusted, index) if isinstance(adjusted, list) else None),
                    "volume": as_int(volume),
                }
            )
        )
    return bars


def _status(exchange: str, meta: dict[str, Any]) -> MarketStatus:
    periods = meta.get("currentTradingPeriod")
    if not isinstance(periods, dict):
        raise MarketDataError("unavailable")
    observed = unix_time(meta.get("regularMarketTime")) if meta.get("regularMarketTime") is not None else datetime.now(UTC)
    state = "closed"
    for name, status in (("pre", "pre-open"), ("regular", "open"), ("post", "post-market")):
        window = periods.get(name)
        if not isinstance(window, dict):
            continue
        start = unix_time(window.get("start"))
        end = unix_time(window.get("end"))
        if start <= observed < end:
            state = status
            break
    return MarketStatus(exchange=exchange, status=state, observed_at=observed, source="yahoo")


def _last_bar_field(chart: dict[str, Any], field: str) -> object:
    indicators = chart.get("indicators")
    if not isinstance(indicators, dict):
        return None
    quote_rows = indicators.get("quote")
    if not isinstance(quote_rows, list) or not quote_rows or not isinstance(quote_rows[0], dict):
        return None
    values = quote_rows[0].get(field)
    if not isinstance(values, list):
        return None
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _at(values: object, index: int) -> object:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _text(value: object) -> str | None:
    number = value if isinstance(value, type(None)) else as_decimal(value)
    if number is None:
        return None
    return format(number, "f")


def _market_code(code: str) -> str:
    if code in {"rate_limited", "unauthorized", "not_found", "malformed", "unavailable", "unsupported_exchange"}:
        return code
    return "unavailable"
