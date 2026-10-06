from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer


def _decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


class StockRef(BaseModel):
    id: UUID
    symbol: str
    exchange: str
    company_name: str


class FundamentalMetadata(BaseModel):
    """Source and freshness. `filing_date_known` is false when publication time was not supplied."""

    currency: str
    source: str | None
    data_as_of: datetime | None
    is_available: bool
    is_stale: bool
    filing_date_known: bool
    supplemented_from_period: str | None = None


class FundamentalPeriod(BaseModel):
    fiscal_period: str
    fiscal_period_type: str
    report_date: date
    filing_date: date | None


class FundamentalMetrics(BaseModel):
    """Reported figures. Rates are percentage points. Money is absolute currency units."""

    revenue: Decimal | None = None
    revenue_growth: Decimal | None = None
    ebitda: Decimal | None = None
    ebitda_growth: Decimal | None = None
    operating_profit: Decimal | None = None
    net_income: Decimal | None = None
    profit_growth: Decimal | None = None
    eps: Decimal | None = None
    eps_growth: Decimal | None = None
    book_value_per_share: Decimal | None = None
    roe: Decimal | None = None
    roce: Decimal | None = None
    gross_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    net_margin: Decimal | None = None
    debt_to_equity: Decimal | None = None
    current_ratio: Decimal | None = None
    interest_coverage: Decimal | None = None
    free_cash_flow: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    cfo_to_net_profit: Decimal | None = None
    revenue_cagr_3y: Decimal | None = None
    revenue_cagr_5y: Decimal | None = None

    @field_serializer(
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
        "cfo_to_net_profit",
        "revenue_cagr_3y",
        "revenue_cagr_5y",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return _decimal(value)


class FundamentalReportResponse(BaseModel):
    stock: StockRef
    data: FundamentalMetrics
    period: FundamentalPeriod | None
    metadata: FundamentalMetadata


class FundamentalHistoryResponse(BaseModel):
    stock: StockRef
    total: int
    limit: int
    offset: int
    results: list[FundamentalReportResponse]


class ValuationMetrics(BaseModel):
    """Point-in-time valuation. Multiples are raw. Dividend yield is percentage points."""

    market_price: Decimal | None = None
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    peg_ratio: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    ev_to_sales: Decimal | None = None
    dividend_yield: Decimal | None = None

    @field_serializer(
        "market_price",
        "market_cap",
        "enterprise_value",
        "pe_ratio",
        "pb_ratio",
        "peg_ratio",
        "ev_to_ebitda",
        "ev_to_sales",
        "dividend_yield",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return _decimal(value)


class ValuationResponse(BaseModel):
    stock: StockRef
    data: ValuationMetrics
    snapshot_at: datetime | None
    metadata: FundamentalMetadata


class ValuationHistoryResponse(BaseModel):
    stock: StockRef
    total: int
    limit: int
    offset: int
    results: list[ValuationResponse]


class SectorMetric(BaseModel):
    metric: str
    stock_value: Decimal | None
    benchmark_value: Decimal | None
    difference: Decimal | None

    @field_serializer("stock_value", "benchmark_value", "difference", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return _decimal(value)


class SectorComparisonResponse(BaseModel):
    stock: StockRef
    sector: str | None
    calculation_date: date | None
    source: str | None
    methodology: str | None
    metrics: list[SectorMetric]
    benchmark_available: bool
