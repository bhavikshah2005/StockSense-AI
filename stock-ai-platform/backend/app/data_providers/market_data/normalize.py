"""Turn an internal field mapping into provider models.

Vendor adapters must rename the vendor's own JSON into these keys first.
This module does not recognize any vendor's response format.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.data_providers.market_data.base import InstrumentRef, PriceBar, Quote
from app.data_providers.market_data.errors import MALFORMED, MarketDataError

_MONEY_SCALE = Decimal("0.0001")


def normalize_quote(raw: Mapping[str, Any], instrument: InstrumentRef) -> Quote:
    change = _optional_money(raw.get("change"))
    change_percent = _optional_money(raw.get("change_percent"))
    return Quote(
        symbol=_text(raw.get("symbol"), "symbol"),
        exchange=_text(raw.get("exchange"), "exchange"),
        currency=_text(raw.get("currency"), "currency"),
        current_price=_money(raw.get("current_price"), "current_price"),
        previous_close=_optional_money(raw.get("previous_close")),
        change=change,
        change_percent=change_percent,
        open=_optional_money(raw.get("open")),
        high=_optional_money(raw.get("high")),
        low=_optional_money(raw.get("low")),
        volume=_optional_volume(raw.get("volume")),
        market_timestamp=_timestamp(raw.get("market_timestamp")),
        delayed=_bool(raw.get("delayed", False)),
        delay_minutes=_optional_delay(raw.get("delay_minutes")),
    )


def normalize_bar(raw: Mapping[str, Any]) -> PriceBar:
    return PriceBar(
        timestamp=_timestamp(raw.get("timestamp")),
        interval=_text(raw.get("interval"), "interval"),
        open=_money(raw.get("open"), "open"),
        high=_money(raw.get("high"), "high"),
        low=_money(raw.get("low"), "low"),
        close=_money(raw.get("close"), "close"),
        adjusted_close=_optional_money(raw.get("adjusted_close")),
        volume=_volume(raw.get("volume")),
    )


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataError(MALFORMED)
    return value.strip()


def _money(value: object, field: str) -> Decimal:
    parsed = _decimal(value, field)
    return parsed.quantize(_MONEY_SCALE)


def _optional_money(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return _money(value, "price")


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise MarketDataError(MALFORMED)
    try:
        number = Decimal(value if isinstance(value, str) else str(value))
    except (InvalidOperation, ValueError):
        raise MarketDataError(MALFORMED) from None
    if not number.is_finite():
        raise MarketDataError(MALFORMED)
    return number


def _volume(value: object) -> int:
    parsed = _optional_volume(value)
    if parsed is None:
        raise MarketDataError(MALFORMED)
    return parsed


def _optional_volume(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise MarketDataError(MALFORMED)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise MarketDataError(MALFORMED)


def _optional_delay(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, int):
        raise MarketDataError(MALFORMED)
    if value < 0:
        raise MarketDataError(MALFORMED)
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise MarketDataError(MALFORMED)
    return value


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise MarketDataError(MALFORMED) from None
    else:
        raise MarketDataError(MALFORMED)
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise MarketDataError(MALFORMED)
    return parsed
