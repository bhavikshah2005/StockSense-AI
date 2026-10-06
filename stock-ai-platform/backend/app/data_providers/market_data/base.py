from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

STORAGE_INTERVALS: frozenset[str] = frozenset({"1d", "1h", "15m", "5m"})
INTRADAY_INTERVALS: frozenset[str] = frozenset({"1h", "15m", "5m"})
MARKET_SESSION_STATES: frozenset[str] = frozenset(
    {"open", "closed", "pre-open", "post-market", "holiday"}
)


@dataclass(frozen=True)
class InstrumentRef:
    """A listing the provider may be asked about. Exchange comes from the stock row."""

    symbol: str
    exchange: str
    currency: str
    country: str


@dataclass(frozen=True)
class Quote:
    """Normalized latest trade data. Monetary fields are Decimal, not binary floats."""

    symbol: str
    exchange: str
    currency: str
    current_price: Decimal
    previous_close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    market_timestamp: datetime
    delayed: bool
    delay_minutes: int | None


@dataclass(frozen=True)
class PriceBar:
    """One OHLCV bar already expressed in the internal model."""

    timestamp: datetime
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int


@dataclass(frozen=True)
class MarketStatus:
    """Session state supplied by a provider or a configured market calendar."""

    exchange: str
    status: str
    observed_at: datetime
    source: str


class MarketDataProvider(ABC):
    """Quotes, historical bars, and session status.

    Services depend on this type. A vendor adapter translates that vendor's
    payload into these models before returning.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier. This is not a secret."""

    @property
    @abstractmethod
    def supported_intervals(self) -> frozenset[str]:
        """Intervals this adapter can request. Empty until a vendor is connected."""

    @abstractmethod
    def get_quote(self, instrument: InstrumentRef) -> Quote:
        """Return the latest quote for one listing."""

    @abstractmethod
    def get_historical_prices(
        self,
        instrument: InstrumentRef,
        *,
        start: date,
        end: date,
        interval: str,
    ) -> list[PriceBar]:
        """Return bars inside the requested range for one supported interval."""

    @abstractmethod
    def get_market_status(self, exchange: str) -> MarketStatus:
        """Return the session state reported by the provider for one exchange."""
