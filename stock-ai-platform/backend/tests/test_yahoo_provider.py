from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.data_providers.fundamentals.base import FundamentalDataProvider
from app.data_providers.market_data.base import InstrumentRef
from app.data_providers.yahoo.fundamentals import YahooFundamentalDataProvider
from app.data_providers.yahoo.http import YahooClient
from app.data_providers.yahoo.market import YahooMarketDataProvider

TCS = InstrumentRef(symbol="TCS", exchange="NSE", currency="INR", country="IN")
STAMP = int(datetime(2026, 9, 23, 10, 0, tzinfo=UTC).timestamp())


def _client(handler) -> YahooClient:
    return YahooClient(transport=httpx.MockTransport(handler))


def test_quote_and_daily_bar_come_from_the_chart_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path in {"/v8/finance/chart/TCS.NS", "/v8/finance/chart/%5ENSEI"} or request.url.path.endswith("NSEI")
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "currency": "INR",
                                "regularMarketPrice": 2100.5,
                                "chartPreviousClose": 2000,
                                "regularMarketDayHigh": 2110,
                                "regularMarketDayLow": 2050,
                                "regularMarketVolume": 1000,
                                "regularMarketTime": STAMP,
                                "currentTradingPeriod": {
                                    "regular": {"start": STAMP - 60, "end": STAMP + 60},
                                },
                            },
                            "timestamp": [STAMP],
                            "indicators": {
                                "quote": [
                                    {"open": [2080], "high": [2110], "low": [2050], "close": [2100.5], "volume": [1000]}
                                ],
                                "adjclose": [{"adjclose": [2100.5]}],
                            },
                        }
                    ],
                    "error": None,
                }
            },
        )

    provider = YahooMarketDataProvider(_client(handler))
    quote = provider.get_quote(TCS)
    assert quote.symbol == "TCS"
    assert quote.exchange == "NSE"
    assert quote.currency == "INR"
    assert quote.current_price == Decimal("2100.5000")
    assert quote.delayed is True
    bars = provider.get_historical_prices(
        TCS,
        start=datetime(2026, 9, 23, tzinfo=UTC).date(),
        end=datetime(2026, 9, 23, tzinfo=UTC).date(),
        interval="1d",
    )
    assert len(bars) == 1
    assert bars[0].close == Decimal("2100.5000")
    assert bars[0].volume == 1000
    status = provider.get_market_status("NSE")
    assert status.status == "open"
    assert status.source == "yahoo"


def test_fundamentals_use_absolute_inr_and_yield_percentage_points() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v8/finance/chart/"):
            return httpx.Response(
                200,
                json={"chart": {"result": [{"meta": {"regularMarketPrice": 2100}}], "error": None}},
            )
        return httpx.Response(
            200,
            json={
                "timeseries": {
                    "result": [
                        {
                            "meta": {"type": ["annualTotalRevenue"]},
                            "annualTotalRevenue": [
                                {"asOfDate": "2025-03-31", "currencyCode": "INR", "reportedValue": {"raw": 80}},
                                {"asOfDate": "2026-03-31", "currencyCode": "INR", "reportedValue": {"raw": 100}},
                            ],
                        },
                        {
                            "meta": {"type": ["annualNetIncome"]},
                            "annualNetIncome": [
                                {"asOfDate": "2026-03-31", "currencyCode": "INR", "reportedValue": {"raw": 10}}
                            ],
                        },
                        {
                            "meta": {"type": ["annualStockholdersEquity"]},
                            "annualStockholdersEquity": [
                                {"asOfDate": "2026-03-31", "currencyCode": "INR", "reportedValue": {"raw": 50}}
                            ],
                        },
                        {
                            "meta": {"type": ["trailingPeRatio"]},
                            "trailingPeRatio": [{"asOfDate": "2026-09-22", "reportedValue": {"raw": 15.5}}],
                        },
                        {
                            "meta": {"type": ["trailingDividendYield"]},
                            "trailingDividendYield": [{"asOfDate": "2026-09-22", "dataValue": 0.0271}],
                        },
                    ],
                    "error": None,
                }
            },
        )

    provider: FundamentalDataProvider = YahooFundamentalDataProvider(_client(handler))
    latest = provider.get_latest_fundamentals(symbol="TCS", exchange="NSE", currency="INR", country="IN")
    assert latest is not None
    assert latest.fiscal_period == "FY2026"
    assert latest.revenue == Decimal("100.00")
    assert latest.filing_date is None
    assert latest.roe == Decimal("20.000000")
    valuation = provider.get_latest_valuation(symbol="TCS", exchange="NSE", currency="INR", country="IN")
    assert valuation is not None
    assert valuation.pe_ratio == Decimal("15.500000")
    assert valuation.dividend_yield == Decimal("2.710000")
    assert valuation.market_price == Decimal("2100.0000")


def test_ratios_come_from_the_same_reported_period() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v8/finance/chart/"):
            return httpx.Response(200, json={"chart": {"result": [{"meta": {}}], "error": None}})
        return httpx.Response(
            200,
            json={
                "timeseries": {
                    "result": [
                        _series("quarterlyTotalRevenue", "2026-06-30", 400),
                        _series("quarterlyOperatingIncome", "2026-06-30", 100),
                        _series("quarterlyNetIncome", "2026-06-30", 80),
                        _series("quarterlyCurrentAssets", "2026-06-30", 220),
                        _series("quarterlyCurrentLiabilities", "2026-06-30", 100),
                        _series("quarterlyInterestExpense", "2026-06-30", 5),
                        _series("quarterlyTotalAssets", "2026-06-30", 600),
                    ],
                    "error": None,
                }
            },
        )

    provider = YahooFundamentalDataProvider(_client(handler))
    latest = provider.get_latest_fundamentals(symbol="TCS", exchange="NSE", currency="INR", country="IN")
    assert latest is not None
    assert latest.operating_margin == Decimal("25.000000")
    assert latest.net_margin == Decimal("20.000000")
    assert latest.current_ratio == Decimal("2.200000")
    assert latest.interest_coverage == Decimal("20.000000")
    assert latest.roce == Decimal("20.000000")


def _series(name: str, day: str, raw: int) -> dict[str, object]:
    return {
        "meta": {"type": [name]},
        name: [{"asOfDate": day, "currencyCode": "INR", "reportedValue": {"raw": raw}}],
    }
