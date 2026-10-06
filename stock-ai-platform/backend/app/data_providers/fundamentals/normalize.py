"""Turn an internal field mapping into provider models.

Vendor adapters must rename the vendor payload into these keys first.
Known aliases, and only these, are accepted because their meaning matches:

- sales -> revenue (operating revenue, absolute currency units)
- profit -> net_income
- eps_basic -> eps (basic earnings per share)
- return_on_equity -> roe (percentage points)
- return_on_capital_employed -> roce (percentage points)
- debt_equity -> debt_to_equity (raw ratio)

Crore, million, and billion scales are not accepted here. The adapter converts them.
"""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.data_providers.fundamentals.base import ReportedFundamental, ValuationReading
from app.data_providers.fundamentals.errors import MALFORMED, FundamentalDataError

_ALIASES = {
    "sales": "revenue",
    "profit": "net_income",
    "eps_basic": "eps",
    "return_on_equity": "roe",
    "return_on_capital_employed": "roce",
    "debt_equity": "debt_to_equity",
}

_REPORT_FIELDS = {
    "fiscal_period",
    "fiscal_period_type",
    "period_end",
    "filing_date",
    "currency",
    "revenue",
    "revenue_growth",
    "ebitda",
    "ebitda_growth",
    "operating_profit",
    "net_income",
    "profit_growth",
    "eps",
    "eps_growth",
    "book_value_per_share",
    "roe",
    "roce",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",
    "free_cash_flow",
    "operating_cash_flow",
    "provider_retrieved_at",
}

_MONEY = {
    "revenue",
    "ebitda",
    "operating_profit",
    "net_income",
    "free_cash_flow",
    "operating_cash_flow",
    "market_price",
    "market_cap",
    "enterprise_value",
}
_PER_SHARE = {"eps", "book_value_per_share"}


def normalize_report(raw: Mapping[str, Any]) -> ReportedFundamental:
    payload = _canonicalize(raw, _REPORT_FIELDS)
    period_type = _text(payload.get("fiscal_period_type"))
    if period_type not in {"annual", "quarterly"}:
        raise FundamentalDataError(MALFORMED)
    period_end = _day(payload.get("period_end"))
    filing = _optional_day(payload.get("filing_date"))
    if filing is not None and filing < period_end:
        raise FundamentalDataError(MALFORMED)
    return ReportedFundamental(
        fiscal_period=_text(payload.get("fiscal_period")),
        fiscal_period_type=period_type,
        period_end=period_end,
        filing_date=filing,
        currency=_currency(payload.get("currency")),
        revenue=_money(payload.get("revenue")),
        revenue_growth=_ratio(payload.get("revenue_growth")),
        ebitda=_money(payload.get("ebitda")),
        ebitda_growth=_ratio(payload.get("ebitda_growth")),
        operating_profit=_money(payload.get("operating_profit")),
        net_income=_money(payload.get("net_income")),
        profit_growth=_ratio(payload.get("profit_growth")),
        eps=_per_share(payload.get("eps")),
        eps_growth=_ratio(payload.get("eps_growth")),
        book_value_per_share=_per_share(payload.get("book_value_per_share")),
        roe=_ratio(payload.get("roe")),
        roce=_ratio(payload.get("roce")),
        gross_margin=_ratio(payload.get("gross_margin")),
        operating_margin=_ratio(payload.get("operating_margin")),
        net_margin=_ratio(payload.get("net_margin")),
        debt_to_equity=_ratio(payload.get("debt_to_equity")),
        current_ratio=_ratio(payload.get("current_ratio")),
        interest_coverage=_ratio(payload.get("interest_coverage")),
        free_cash_flow=_money(payload.get("free_cash_flow")),
        operating_cash_flow=_money(payload.get("operating_cash_flow")),
        provider_retrieved_at=_instant(payload.get("provider_retrieved_at")),
    )


def normalize_valuation(raw: Mapping[str, Any]) -> ValuationReading:
    allowed = {
        "snapshot_at",
        "market_price",
        "market_cap",
        "enterprise_value",
        "pe_ratio",
        "pb_ratio",
        "peg_ratio",
        "ev_to_ebitda",
        "ev_to_sales",
        "dividend_yield",
        "currency",
        "provider_retrieved_at",
    }
    payload = _canonicalize(raw, allowed)
    return ValuationReading(
        snapshot_at=_instant(payload.get("snapshot_at")),
        market_price=_per_share(payload.get("market_price")),
        market_cap=_money(payload.get("market_cap")),
        enterprise_value=_money(payload.get("enterprise_value")),
        pe_ratio=_ratio(payload.get("pe_ratio")),
        pb_ratio=_ratio(payload.get("pb_ratio")),
        peg_ratio=_ratio(payload.get("peg_ratio")),
        ev_to_ebitda=_ratio(payload.get("ev_to_ebitda")),
        ev_to_sales=_ratio(payload.get("ev_to_sales")),
        dividend_yield=_ratio(payload.get("dividend_yield")),
        currency=_currency(payload.get("currency")),
        provider_retrieved_at=_instant(payload.get("provider_retrieved_at")),
    )


def _canonicalize(raw: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in raw.items():
        name = _ALIASES.get(key, key)
        if name not in allowed:
            raise FundamentalDataError(MALFORMED)
        payload[name] = value
    return payload


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 32:
        raise FundamentalDataError(MALFORMED)
    return value.strip()


def _currency(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) != 3:
        raise FundamentalDataError(MALFORMED)
    return value.strip().upper()


def _day(value: object) -> date:
    parsed = _optional_day(value)
    if parsed is None:
        raise FundamentalDataError(MALFORMED)
    return parsed


def _optional_day(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            raise FundamentalDataError(MALFORMED) from None
    raise FundamentalDataError(MALFORMED)


def _instant(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise FundamentalDataError(MALFORMED) from None
    else:
        raise FundamentalDataError(MALFORMED)
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise FundamentalDataError(MALFORMED)
    return parsed


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise FundamentalDataError(MALFORMED)
    try:
        number = Decimal(value if isinstance(value, str) else str(value))
    except (InvalidOperation, ValueError):
        raise FundamentalDataError(MALFORMED) from None
    if not number.is_finite():
        raise FundamentalDataError(MALFORMED)
    return number


def _money(value: object) -> Decimal | None:
    number = _decimal(value)
    if number is None:
        return None
    return number.quantize(Decimal("0.01"))


def _per_share(value: object) -> Decimal | None:
    number = _decimal(value)
    if number is None:
        return None
    return number.quantize(Decimal("0.0001"))


def _ratio(value: object) -> Decimal | None:
    number = _decimal(value)
    if number is None:
        return None
    if abs(number) > Decimal("1000000"):
        raise FundamentalDataError(MALFORMED)
    return number.quantize(Decimal("0.000001"))
