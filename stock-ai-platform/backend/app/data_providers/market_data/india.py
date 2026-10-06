"""Indian market-data provider placeholder.

Wire a real vendor here only after its official API contract is known.
Set the credentials in the backend environment, then add an adapter that
maps that vendor's payload through `normalize_quote` and `normalize_bar`.

This class does not call `MARKET_DATA_BASE_URL`. A configured name or key
is not a license to guess an HTTP API.
"""

from datetime import date

from app.data_providers.market_data.base import (
    InstrumentRef,
    MarketDataProvider,
    MarketStatus,
    PriceBar,
    Quote,
)
from app.data_providers.market_data.errors import NOT_CONFIGURED, UNSUPPORTED_EXCHANGE, MarketDataError
from app.markets.profile import active_market


class UnconfiguredMarketDataProvider(MarketDataProvider):
    """Used when MARKET_DATA_PROVIDER is empty."""

    @property
    def name(self) -> str:
        return "unconfigured"

    @property
    def supported_intervals(self) -> frozenset[str]:
        return frozenset()

    def get_quote(self, instrument: InstrumentRef) -> Quote:
        self._reject_outside_market(instrument)
        raise MarketDataError(NOT_CONFIGURED)

    def get_historical_prices(
        self,
        instrument: InstrumentRef,
        *,
        start: date,
        end: date,
        interval: str,
    ) -> list[PriceBar]:
        self._reject_outside_market(instrument)
        raise MarketDataError(NOT_CONFIGURED)

    def get_market_status(self, exchange: str) -> MarketStatus:
        self._reject_exchange(exchange)
        raise MarketDataError(NOT_CONFIGURED)

    def _reject_outside_market(self, instrument: InstrumentRef) -> None:
        profile = active_market()
        if (
            instrument.country != profile.country
            or instrument.currency != profile.currency
            or instrument.exchange not in profile.exchanges
        ):
            raise MarketDataError(UNSUPPORTED_EXCHANGE)

    def _reject_exchange(self, exchange: str) -> None:
        if exchange not in active_market().exchanges:
            raise MarketDataError(UNSUPPORTED_EXCHANGE)


class IndianMarketDataProvider(UnconfiguredMarketDataProvider):
    """Indian listings only. No vendor HTTP client is attached."""

    def __init__(self, configured_name: str) -> None:
        self._configured_name = configured_name

    @property
    def name(self) -> str:
        return "indian"
