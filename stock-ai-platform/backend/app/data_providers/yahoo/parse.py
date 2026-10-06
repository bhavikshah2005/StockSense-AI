"""Shared parsing for Yahoo numeric payloads. Floats are converted before storage."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from app.data_providers.yahoo.http import YahooStatus

UTC = timezone.utc


def yahoo_symbol(symbol: str, exchange: str) -> str:
    suffix = {"NSE": "NS", "BSE": "BO"}.get(exchange)
    if suffix is None:
        raise YahooStatus("unsupported_exchange")
    cleaned = symbol.strip().upper()
    if not cleaned or any(character.isspace() for character in cleaned):
        raise YahooStatus("malformed")
    return f"{cleaned}.{suffix}"


def as_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, float):
        if isinstance(value, float) and value != value:
            return None
        text = format(value, "f") if isinstance(value, float) else None
        if text is None:
            raise YahooStatus("malformed")
        value = text
    try:
        number = Decimal(value if isinstance(value, str) else str(value))
    except (InvalidOperation, ValueError) as exc:
        raise YahooStatus("malformed") from exc
    if not number.is_finite():
        return None
    return number


def as_int(value: object) -> int | None:
    number = as_decimal(value)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise YahooStatus("malformed")
    return int(number)


def unix_time(value: object) -> datetime:
    number = as_int(value)
    if number is None:
        raise YahooStatus("malformed")
    return datetime.fromtimestamp(number, tz=UTC)


def parse_day(value: object) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise YahooStatus("malformed")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise YahooStatus("malformed") from exc


def series_value(item: dict[str, object]) -> Decimal | None:
    reported = item.get("reportedValue")
    if isinstance(reported, dict):
        return as_decimal(reported.get("raw"))
    if "dataValue" in item:
        return as_decimal(item.get("dataValue"))
    return as_decimal(item.get("raw"))
