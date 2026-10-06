"""Deterministic fundamental math. Percentage results use percentage points."""

from datetime import date
from decimal import Decimal

from app.models.fundamental import Fundamental

_PERCENT = Decimal("0.000001")


def growth_percent(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """(current - previous) / previous, as percentage points. Zero previous is undefined."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / previous * Decimal(100)).quantize(_PERCENT)


def margin_percent(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    """numerator / denominator as percentage points. A zero denominator is undefined."""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator * Decimal(100)).quantize(_PERCENT)


def cagr_percent(start_value: Decimal | None, end_value: Decimal | None, years: int) -> Decimal | None:
    """Compound annual growth. A non-positive start value is left undefined."""
    if start_value is None or end_value is None or years <= 0 or start_value <= 0 or end_value <= 0:
        return None
    ratio = (end_value / start_value) ** (Decimal(1) / Decimal(years))
    return ((ratio - 1) * Decimal(100)).quantize(_PERCENT)


def cfo_to_net_profit(operating_cash_flow: Decimal | None, net_income: Decimal | None) -> Decimal | None:
    """Operating cash flow divided by net income. A zero profit leaves the ratio undefined."""
    if operating_cash_flow is None or net_income is None or net_income == 0:
        return None
    return (operating_cash_flow / net_income).quantize(_PERCENT)


def fill_missing_growth(current: Fundamental, previous: Fundamental | None) -> None:
    """Fill empty margins from this period, and growth only when a prior period exists."""
    if current.net_margin is None:
        current.net_margin = margin_percent(current.net_income, current.revenue)
    if current.operating_margin is None:
        current.operating_margin = margin_percent(current.operating_profit, current.revenue)
    if previous is None:
        return
    if current.revenue_growth is None:
        current.revenue_growth = growth_percent(current.revenue, previous.revenue)
    if current.profit_growth is None:
        current.profit_growth = growth_percent(current.net_income, previous.net_income)
    if current.eps_growth is None:
        current.eps_growth = growth_percent(current.eps, previous.eps)
    if current.ebitda_growth is None:
        current.ebitda_growth = growth_percent(current.ebitda, previous.ebitda)


def annual_cagr(reports: list[Fundamental], years: int) -> Decimal | None:
    """CAGR from an annual report about `years` before the latest annual report."""
    annual = [row for row in reports if row.fiscal_period_type == "annual" and row.revenue is not None]
    if len(annual) < 2:
        return None
    latest = max(annual, key=lambda row: row.report_date)
    target = date(latest.report_date.year - years, latest.report_date.month, 1)
    window = [
        row
        for row in annual
        if row.report_date < latest.report_date and abs((row.report_date - target).days) <= 120
    ]
    if not window:
        return None
    start = min(window, key=lambda row: abs((row.report_date - target).days))
    elapsed = (latest.report_date - start.report_date).days / 365.25
    if elapsed < years - 0.5:
        return None
    return cagr_percent(start.revenue, latest.revenue, years)
