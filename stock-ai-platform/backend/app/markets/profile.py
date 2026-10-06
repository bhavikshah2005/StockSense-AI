from dataclasses import dataclass


@dataclass(frozen=True)
class MarketProfile:
    """One supported market. Business rules read this object instead of exchange literals."""

    code: str
    country: str
    country_name: str
    currency: str
    exchanges: tuple[str, ...]


INDIA = MarketProfile(
    code="IN",
    country="IN",
    country_name="India",
    currency="INR",
    exchanges=("NSE", "BSE"),
)


def active_market() -> MarketProfile:
    """The market for this release. Another profile can be selected later."""
    return INDIA
