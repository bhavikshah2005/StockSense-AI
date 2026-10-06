import csv
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.markets.profile import MarketProfile, active_market


@dataclass(frozen=True)
class IndianListing:
    symbol: str
    company_name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    industry: str | None
    isin: str | None


@dataclass(frozen=True)
class _Company:
    symbol: str
    company_name: str
    sector: str
    industry: str
    isin: str | None


_MASTER_PATH = Path(__file__).with_name("equity_master.csv")

# Sector labels for the original starter names. equity_master.csv is the full
# company list: NSE main board, NSE SME, and BSE equity groups.
_COMPANIES: tuple[_Company, ...] = (
    _Company("RELIANCE", "Reliance Industries Limited", "Energy", "Oil and Gas", "INE002A01018"),
    _Company("TCS", "Tata Consultancy Services Limited", "Information Technology", "IT Services", "INE467B01029"),
    _Company("INFY", "Infosys Limited", "Information Technology", "IT Services", "INE009A01021"),
    _Company("HDFCBANK", "HDFC Bank Limited", "Financial Services", "Banks", "INE040A01034"),
    _Company("ICICIBANK", "ICICI Bank Limited", "Financial Services", "Banks", "INE090A01021"),
    _Company("SBIN", "State Bank of India", "Financial Services", "Banks", "INE062A01020"),
    _Company("ITC", "ITC Limited", "Consumer Staples", "FMCG", "INE154A01025"),
    _Company("HINDUNILVR", "Hindustan Unilever Limited", "Consumer Staples", "FMCG", "INE030A01027"),
    _Company("BHARTIARTL", "Bharti Airtel Limited", "Communication Services", "Telecom", "INE397D01024"),
    _Company("LT", "Larsen & Toubro Limited", "Industrials", "Construction", "INE018A01030"),
    _Company("KOTAKBANK", "Kotak Mahindra Bank Limited", "Financial Services", "Banks", "INE237A01028"),
    _Company("AXISBANK", "Axis Bank Limited", "Financial Services", "Banks", "INE238A01034"),
    _Company("WIPRO", "Wipro Limited", "Information Technology", "IT Services", "INE075A01022"),
    _Company("HCLTECH", "HCL Technologies Limited", "Information Technology", "IT Services", "INE860A01027"),
    _Company("SUNPHARMA", "Sun Pharmaceutical Industries Limited", "Health Care", "Pharmaceuticals", "INE044A01036"),
    _Company("MARUTI", "Maruti Suzuki India Limited", "Consumer Discretionary", "Automobiles", "INE585B01010"),
    _Company("ASIANPAINT", "Asian Paints Limited", "Consumer Discretionary", "Paints", "INE021A01026"),
)


class IndianStockMetadataProvider(ABC):
    """Listing metadata for the Indian market. Quotes are a separate provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier."""

    @abstractmethod
    def listings(self, market: MarketProfile) -> Sequence[IndianListing]:
        """Return listings for the given market profile."""


class BundledIndianCatalog(IndianStockMetadataProvider):
    """NSE and BSE equity master shipped with the app."""

    @property
    def name(self) -> str:
        return "bundled-indian-catalog"

    def listings(self, market: MarketProfile) -> Sequence[IndianListing]:
        allowed = set(market.exchanges)
        return [row for row in _load_equity_master(market) if row.exchange in allowed]


class UnconfiguredIndianStockMetadataProvider(IndianStockMetadataProvider):
    @property
    def name(self) -> str:
        return "unconfigured"

    def listings(self, market: MarketProfile) -> Sequence[IndianListing]:
        del market
        raise NotImplementedError("No Indian stock metadata provider is configured.")


def get_indian_metadata_provider() -> IndianStockMetadataProvider:
    """The bundled catalog is the configured source until a vendor is selected."""
    return BundledIndianCatalog()


def bundled_listings() -> Sequence[IndianListing]:
    return get_indian_metadata_provider().listings(active_market())


@lru_cache
def _load_equity_master(market: MarketProfile) -> tuple[IndianListing, ...]:
    """Read the shipped equity master. Quotes stay on the market-data provider."""
    sectors = {company.symbol: company for company in _COMPANIES}
    rows: list[IndianListing] = []
    with _MASTER_PATH.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            symbol = record["symbol"].strip().upper()
            exchange = record["exchange"].strip().upper()
            if exchange not in market.exchanges:
                continue
            known = sectors.get(symbol)
            isin = record["isin"].strip().upper() or None
            rows.append(
                IndianListing(
                    symbol=symbol,
                    company_name=record["company_name"].strip(),
                    exchange=exchange,
                    country=market.country,
                    currency=market.currency,
                    sector=known.sector if known else None,
                    industry=known.industry if known else None,
                    isin=isin or (known.isin if known else None),
                )
            )
    return tuple(rows)
