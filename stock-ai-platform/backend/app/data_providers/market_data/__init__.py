from app.core.config import get_settings
from app.data_providers.market_data.base import (
    InstrumentRef,
    MarketDataProvider,
    MarketStatus,
    PriceBar,
    Quote,
)
from app.data_providers.market_data.india import IndianMarketDataProvider, UnconfiguredMarketDataProvider


def get_market_data_provider() -> MarketDataProvider:
    """Select the market-data adapter from MARKET_DATA_PROVIDER.

    An empty value or `yahoo` uses the Yahoo Finance chart feed for NSE and BSE.
    Any other value keeps the Indian placeholder, which does not call a vendor.
    """
    configured = get_settings().market_data_provider.strip().lower()
    if configured in {"", "yahoo"}:
        from app.data_providers.yahoo.market import YahooMarketDataProvider

        return YahooMarketDataProvider()
    return IndianMarketDataProvider(configured_name=configured)


__all__ = [
    "InstrumentRef",
    "IndianMarketDataProvider",
    "MarketDataProvider",
    "MarketStatus",
    "PriceBar",
    "Quote",
    "UnconfiguredMarketDataProvider",
    "get_market_data_provider",
]
