"""Yahoo Finance fundamentals timeseries for NSE and BSE.

Reported money is Yahoo's `reportedValue.raw` in absolute INR.
Trailing dividend yield `dataValue` is a fraction and is stored as percentage points
(0.0271 becomes 2.71). Filing dates are not in this feed, so `filing_date` stays
empty and availability is the retrieval time.

ROE is net income divided by stockholders' equity when equity is positive.
Debt/equity is total debt divided by equity when equity is not zero.
Gross, operating, and net margins are the matching profit divided by revenue
when revenue is positive.
Current ratio is current assets divided by current liabilities when liabilities
are positive. Interest coverage is operating profit divided by interest expense
when interest expense is positive. ROCE is operating profit divided by capital
employed (total assets minus current liabilities) when that capital is positive.
EV/EBITDA and EV/Sales use the latest annual EBITDA or revenue on or before the
valuation date. Those ratios stay empty when the denominator is missing or not positive.
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal

from app.core.config import get_settings
from app.data_providers.fundamentals.base import FundamentalDataProvider, ReportedFundamental, ValuationReading
from app.data_providers.fundamentals.errors import FundamentalDataError
from app.data_providers.yahoo.http import DEFAULT_BASE_URL, YahooClient, YahooStatus
from app.data_providers.yahoo.parse import as_decimal, parse_day, series_value, yahoo_symbol
from app.markets.profile import active_market
from app.markets.time import IST

_ANNUAL = {
    "annualTotalRevenue": "revenue",
    "annualEBITDA": "ebitda",
    "annualOperatingIncome": "operating_profit",
    "annualNetIncome": "net_income",
    "annualBasicEPS": "eps",
    "annualGrossProfit": "gross_profit",
    "annualFreeCashFlow": "free_cash_flow",
    "annualOperatingCashFlow": "operating_cash_flow",
    "annualTotalDebt": "total_debt",
    "annualStockholdersEquity": "equity",
    "annualCurrentAssets": "current_assets",
    "annualCurrentLiabilities": "current_liabilities",
    "annualInterestExpense": "interest_expense",
    "annualTotalAssets": "total_assets",
}
_QUARTERLY = {
    "quarterlyTotalRevenue": "revenue",
    "quarterlyNetIncome": "net_income",
    "quarterlyBasicEPS": "eps",
    "quarterlyEBITDA": "ebitda",
    "quarterlyOperatingIncome": "operating_profit",
    "quarterlyGrossProfit": "gross_profit",
    "quarterlyFreeCashFlow": "free_cash_flow",
    "quarterlyOperatingCashFlow": "operating_cash_flow",
    "quarterlyTotalDebt": "total_debt",
    "quarterlyStockholdersEquity": "equity",
    "quarterlyCurrentAssets": "current_assets",
    "quarterlyCurrentLiabilities": "current_liabilities",
    "quarterlyInterestExpense": "interest_expense",
    "quarterlyTotalAssets": "total_assets",
}
_VALUATION = {
    "trailingPeRatio": "pe_ratio",
    "trailingPbRatio": "pb_ratio",
    "trailingPegRatio": "peg_ratio",
    "trailingMarketCap": "market_cap",
    "trailingEnterpriseValue": "enterprise_value",
    "trailingDividendYield": "dividend_yield",
}
_PERCENT = Decimal("0.000001")
_MONEY = Decimal("0.01")
_PER_SHARE = Decimal("0.0001")


class YahooFundamentalDataProvider(FundamentalDataProvider):
    def __init__(self, client: YahooClient | None = None) -> None:
        settings = get_settings()
        configured = settings.fundamental_api_base_url.strip() or settings.market_data_base_url.strip()
        self._client = client or YahooClient(configured or DEFAULT_BASE_URL)

    @property
    def name(self) -> str:
        return "yahoo"

    def get_latest_fundamentals(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ReportedFundamental | None:
        history = self.get_fundamental_history(symbol=symbol, exchange=exchange, currency=currency, country=country)
        return history[-1] if history else None

    def get_fundamental_history(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ReportedFundamental]:
        self._reject(exchange, currency, country)
        rows = self._series(symbol, exchange, list({**_ANNUAL, **_QUARTERLY}))
        reports = _reports(rows, currency)
        return [row for row in reports if _in_range(row.period_end, start, end)]

    def get_latest_valuation(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ValuationReading | None:
        history = self.get_valuation_history(symbol=symbol, exchange=exchange, currency=currency, country=country)
        return history[-1] if history else None

    def get_valuation_history(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ValuationReading]:
        self._reject(exchange, currency, country)
        valuation = self._series(symbol, exchange, list(_VALUATION))
        annual = self._series(symbol, exchange, ["annualEBITDA", "annualTotalRevenue"])
        readings = _valuations(valuation, annual, currency)
        price = _latest_price(self._client, symbol, exchange)
        if readings and price is not None:
            latest = readings[-1]
            readings[-1] = ValuationReading(
                snapshot_at=latest.snapshot_at,
                market_price=price,
                market_cap=latest.market_cap,
                enterprise_value=latest.enterprise_value,
                pe_ratio=latest.pe_ratio,
                pb_ratio=latest.pb_ratio,
                peg_ratio=latest.peg_ratio,
                ev_to_ebitda=latest.ev_to_ebitda,
                ev_to_sales=latest.ev_to_sales,
                dividend_yield=latest.dividend_yield,
                currency=latest.currency,
                provider_retrieved_at=latest.provider_retrieved_at,
            )
        return [row for row in readings if _in_range(row.snapshot_at.astimezone(IST).date(), start, end)]

    def _series(self, symbol: str, exchange: str, names: list[str]) -> dict[str, list[dict[str, object]]]:
        now = int(datetime.now(UTC).timestamp())
        try:
            payload = self._client.get_json(
                f"/ws/fundamentals-timeseries/v1/finance/timeseries/{yahoo_symbol(symbol, exchange)}",
                {"type": ",".join(names), "period1": "0", "period2": str(now)},
            )
        except YahooStatus as exc:
            raise FundamentalDataError(_fundamental_code(exc.code)) from None
        timeseries = payload.get("timeseries")
        if not isinstance(timeseries, dict):
            raise FundamentalDataError("malformed")
        result = timeseries.get("result")
        if result is None:
            return {}
        if not isinstance(result, list):
            raise FundamentalDataError("malformed")
        parsed: dict[str, list[dict[str, object]]] = {}
        allowed = set(names)
        for row in result:
            if not isinstance(row, dict):
                continue
            meta = row.get("meta")
            if not isinstance(meta, dict):
                continue
            kind = meta.get("type")
            name = kind[0] if isinstance(kind, list) and kind else None
            if not isinstance(name, str) or name not in allowed:
                continue
            series = row.get(name)
            if isinstance(series, list):
                parsed[name] = [item for item in series if isinstance(item, dict)]
        return parsed

    def _reject(self, exchange: str, currency: str, country: str) -> None:
        profile = active_market()
        if exchange not in profile.exchanges or currency != profile.currency or country != profile.country:
            raise FundamentalDataError("unsupported_exchange")


def _reports(rows: dict[str, list[dict[str, object]]], currency: str) -> list[ReportedFundamental]:
    grouped: dict[tuple[str, date], dict[str, Decimal]] = {}
    currencies: dict[tuple[str, date], str] = {}
    for yahoo_name, field in {**_ANNUAL, **_QUARTERLY}.items():
        period_type = "annual" if yahoo_name in _ANNUAL else "quarterly"
        for item in rows.get(yahoo_name, []):
            if "asOfDate" not in item:
                continue
            number = series_value(item)
            if number is None:
                continue
            key = (period_type, parse_day(item.get("asOfDate")))
            grouped.setdefault(key, {})[field] = number
            code = item.get("currencyCode")
            if isinstance(code, str) and code.strip():
                currencies[key] = code.strip().upper()
    reports: list[ReportedFundamental] = []
    retrieved = datetime.now(UTC)
    for (period_type, period_end), values in sorted(grouped.items(), key=lambda item: item[0][1]):
        if currencies.get((period_type, period_end), currency) != currency:
            continue
        revenue = values.get("revenue")
        equity = values.get("equity")
        net_income = values.get("net_income")
        operating_profit = values.get("operating_profit")
        current_liabilities = values.get("current_liabilities")
        total_assets = values.get("total_assets")
        capital_employed = None
        if total_assets is not None and current_liabilities is not None:
            capital_employed = total_assets - current_liabilities
        reports.append(
            ReportedFundamental(
                fiscal_period=_label(period_type, period_end),
                fiscal_period_type=period_type,
                period_end=period_end,
                filing_date=None,
                currency=currency,
                revenue=_money(revenue),
                revenue_growth=None,
                ebitda=_money(values.get("ebitda")),
                ebitda_growth=None,
                operating_profit=_money(operating_profit),
                net_income=_money(net_income),
                profit_growth=None,
                eps=_per_share(values.get("eps")),
                eps_growth=None,
                book_value_per_share=None,
                roe=_percent(net_income, equity),
                roce=_percent(operating_profit, capital_employed),
                gross_margin=_percent(values.get("gross_profit"), revenue),
                operating_margin=_percent(operating_profit, revenue),
                net_margin=_percent(net_income, revenue),
                debt_to_equity=_ratio(values.get("total_debt"), equity),
                current_ratio=_positive_ratio(values.get("current_assets"), current_liabilities),
                interest_coverage=_positive_ratio(operating_profit, values.get("interest_expense")),
                free_cash_flow=_money(values.get("free_cash_flow")),
                operating_cash_flow=_money(values.get("operating_cash_flow")),
                provider_retrieved_at=retrieved,
            )
        )
    return [row for row in reports if _has_metric(row)]


def _valuations(
    rows: dict[str, list[dict[str, object]]],
    annual: dict[str, list[dict[str, object]]],
    currency: str,
) -> list[ValuationReading]:
    grouped: dict[date, dict[str, Decimal]] = {}
    for yahoo_name, field in _VALUATION.items():
        for item in rows.get(yahoo_name, []):
            if "asOfDate" not in item:
                continue
            number = series_value(item)
            if number is None:
                continue
            if field == "dividend_yield":
                number = (number * Decimal(100)).quantize(_PERCENT)
            grouped.setdefault(parse_day(item.get("asOfDate")), {})[field] = number
    ebitda = _dated(annual.get("annualEBITDA", []))
    revenue = _dated(annual.get("annualTotalRevenue", []))
    retrieved = datetime.now(UTC)
    readings: list[ValuationReading] = []
    for day, values in sorted(grouped.items()):
        enterprise = values.get("enterprise_value")
        readings.append(
            ValuationReading(
                snapshot_at=datetime.combine(day, time(15, 30), tzinfo=IST),
                market_price=None,
                market_cap=_money(values.get("market_cap")),
                enterprise_value=_money(enterprise),
                pe_ratio=_ratio_value(values.get("pe_ratio")),
                pb_ratio=_ratio_value(values.get("pb_ratio")),
                peg_ratio=_ratio_value(values.get("peg_ratio")),
                ev_to_ebitda=_multiple(enterprise, _on_or_before(ebitda, day)),
                ev_to_sales=_multiple(enterprise, _on_or_before(revenue, day)),
                dividend_yield=_ratio_value(values.get("dividend_yield")),
                currency=currency,
                provider_retrieved_at=retrieved,
            )
        )
    return readings


def _latest_price(client: YahooClient, symbol: str, exchange: str) -> Decimal | None:
    try:
        payload = client.get_json(
            f"/v8/finance/chart/{yahoo_symbol(symbol, exchange)}",
            {"interval": "1d", "range": "1d"},
        )
    except (YahooStatus, TimeoutError, OSError):
        return None
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        return None
    result = chart.get("result")
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        return None
    meta = result[0].get("meta")
    if not isinstance(meta, dict):
        return None
    price = as_decimal(meta.get("regularMarketPrice"))
    if price is None:
        return None
    return price.quantize(_PER_SHARE)


def _dated(series: list[dict[str, object]]) -> list[tuple[date, Decimal]]:
    points: list[tuple[date, Decimal]] = []
    for item in series:
        if "asOfDate" not in item:
            continue
        number = series_value(item)
        if number is None:
            continue
        points.append((parse_day(item.get("asOfDate")), number))
    return sorted(points)


def _on_or_before(points: list[tuple[date, Decimal]], day: date) -> Decimal | None:
    chosen: Decimal | None = None
    for point_day, value in points:
        if point_day <= day:
            chosen = value
        else:
            break
    return chosen


def _label(period_type: str, period_end: date) -> str:
    fiscal_year = period_end.year + 1 if period_end.month >= 4 else period_end.year
    if period_type == "annual":
        return f"FY{fiscal_year}"
    quarter = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}[period_end.month]
    return f"Q{quarter}FY{fiscal_year}"


def _has_metric(row: ReportedFundamental) -> bool:
    return any(
        getattr(row, field) is not None
        for field in (
            "revenue",
            "ebitda",
            "operating_profit",
            "net_income",
            "eps",
            "roe",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "debt_to_equity",
            "current_ratio",
            "interest_coverage",
            "roce",
            "free_cash_flow",
            "operating_cash_flow",
        )
    )


def _in_range(day: date, start: date | None, end: date | None) -> bool:
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_MONEY)


def _per_share(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_PER_SHARE)


def _ratio_value(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_PERCENT)


def _percent(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator * Decimal(100)).quantize(_PERCENT)


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return (numerator / denominator).quantize(_PERCENT)


def _positive_ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(_PERCENT)


def _multiple(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(_PERCENT)


def _fundamental_code(code: str) -> str:
    if code in {"rate_limited", "unauthorized", "not_found", "malformed", "unavailable", "unsupported_exchange"}:
        return code
    return "unavailable"
