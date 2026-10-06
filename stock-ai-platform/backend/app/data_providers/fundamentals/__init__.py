from datetime import date

from app.core.config import get_settings

from app.data_providers.fundamentals.base import FundamentalDataProvider, ReportedFundamental, ValuationReading
from app.data_providers.fundamentals.errors import NOT_CONFIGURED, UNSUPPORTED_EXCHANGE, FundamentalDataError
from app.markets.profile import active_market


class UnconfiguredFundamentalDataProvider(FundamentalDataProvider):
    """Used when FUNDAMENTAL_DATA_PROVIDER is empty."""

    @property
    def name(self) -> str:
        return "unconfigured"

    def get_latest_fundamentals(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ReportedFundamental | None:
        self._reject(exchange, currency, country)
        raise FundamentalDataError(NOT_CONFIGURED)

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
        del start, end
        self._reject(exchange, currency, country)
        raise FundamentalDataError(NOT_CONFIGURED)

    def get_latest_valuation(
        self,
        *,
        symbol: str,
        exchange: str,
        currency: str,
        country: str,
    ) -> ValuationReading | None:
        self._reject(exchange, currency, country)
        raise FundamentalDataError(NOT_CONFIGURED)

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
        del start, end
        self._reject(exchange, currency, country)
        raise FundamentalDataError(NOT_CONFIGURED)

    def _reject(self, exchange: str, currency: str, country: str) -> None:
        profile = active_market()
        if exchange not in profile.exchanges or currency != profile.currency or country != profile.country:
            raise FundamentalDataError(UNSUPPORTED_EXCHANGE)


class IndianFundamentalDataProvider(UnconfiguredFundamentalDataProvider):
    """Indian listings only. No vendor HTTP client is attached."""

    def __init__(self, configured_name: str) -> None:
        if not configured_name.strip():
            raise ValueError("FUNDAMENTAL_DATA_PROVIDER is empty")

    @property
    def name(self) -> str:
        return "indian"


def get_fundamental_data_provider() -> FundamentalDataProvider:
    """Select the adapter from FUNDAMENTAL_DATA_PROVIDER.

    An empty value or `yahoo` uses Yahoo Finance fundamentals timeseries.
    Any other value keeps the Indian placeholder, which does not call a vendor.
    """
    configured = get_settings().fundamental_data_provider.strip().lower()
    if configured in {"", "yahoo"}:
        from app.data_providers.yahoo.fundamentals import YahooFundamentalDataProvider

        return YahooFundamentalDataProvider()
    return IndianFundamentalDataProvider(configured)
