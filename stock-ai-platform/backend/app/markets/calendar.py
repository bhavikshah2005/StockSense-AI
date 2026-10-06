"""Market-session source.

The first release has no official holiday calendar and no provider session
feed. This module therefore reports that the session is unknown. It does not
infer open or closed from the machine clock.
"""

from abc import ABC, abstractmethod

from app.data_providers.market_data.base import MarketStatus


class MarketCalendar(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable calendar identifier."""

    @abstractmethod
    def status(self, exchange: str) -> MarketStatus | None:
        """Return a session when this source can determine one."""


class UnconfiguredMarketCalendar(MarketCalendar):
    @property
    def name(self) -> str:
        return "unconfigured"

    def status(self, exchange: str) -> MarketStatus | None:
        return None


def get_market_calendar() -> MarketCalendar:
    return UnconfiguredMarketCalendar()
