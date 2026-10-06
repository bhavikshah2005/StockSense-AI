from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class ReportedFundamental:
    """One reported period. Money is absolute currency units. Rates are percentage points."""

    fiscal_period: str
    fiscal_period_type: str
    period_end: date
    filing_date: date | None
    currency: str
    revenue: Decimal | None
    revenue_growth: Decimal | None
    ebitda: Decimal | None
    ebitda_growth: Decimal | None
    operating_profit: Decimal | None
    net_income: Decimal | None
    profit_growth: Decimal | None
    eps: Decimal | None
    eps_growth: Decimal | None
    book_value_per_share: Decimal | None
    roe: Decimal | None
    roce: Decimal | None
    gross_margin: Decimal | None
    operating_margin: Decimal | None
    net_margin: Decimal | None
    debt_to_equity: Decimal | None
    current_ratio: Decimal | None
    interest_coverage: Decimal | None
    free_cash_flow: Decimal | None
    operating_cash_flow: Decimal | None
    provider_retrieved_at: datetime


@dataclass(frozen=True)
class ValuationReading:
    """One valuation instant. Multiples are raw. Yield is percentage points."""

    snapshot_at: datetime
    market_price: Decimal | None
    market_cap: Decimal | None
    enterprise_value: Decimal | None
    pe_ratio: Decimal | None
    pb_ratio: Decimal | None
    peg_ratio: Decimal | None
    ev_to_ebitda: Decimal | None
    ev_to_sales: Decimal | None
    dividend_yield: Decimal | None
    currency: str
    provider_retrieved_at: datetime


class FundamentalDataProvider(ABC):
    """Reported financials and valuation snapshots. Adapters translate vendor payloads."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier. This is not a secret."""

    @abstractmethod
    def get_latest_fundamentals(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ReportedFundamental | None:
        """Return the newest reported period, or None when the vendor has none."""

    @abstractmethod
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
        """Return reported periods. `start` and `end` filter on the period end."""

    @abstractmethod
    def get_latest_valuation(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ValuationReading | None:
        """Return the newest valuation instant, or None when the vendor has none."""

    @abstractmethod
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
        """Return valuation instants. `start` and `end` filter on the snapshot date."""
