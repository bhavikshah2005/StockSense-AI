import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.data_providers.fundamentals import (
    IndianFundamentalDataProvider,
    UnconfiguredFundamentalDataProvider,
    get_fundamental_data_provider,
)
from app.data_providers.fundamentals.base import FundamentalDataProvider, ReportedFundamental, ValuationReading
from app.data_providers.fundamentals.errors import FundamentalDataError
from app.data_providers.fundamentals.normalize import normalize_report, normalize_valuation
from app.main import app
from app.markets.time import IST
from app.models import Fundamental, SectorBenchmark, Stock, ValuationSnapshot
from app.services.fundamental_cache import MemoryFundamentalCache, get_fundamental_cache
from app.services.fundamental_math import cagr_percent, growth_percent, margin_percent
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"
RETRIEVED = datetime(2026, 5, 12, 4, 30, tzinfo=UTC)


class RecordingProvider(FundamentalDataProvider):
    def __init__(
        self,
        reports: list[ReportedFundamental] | None = None,
        valuations: list[ValuationReading] | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.reports = [] if reports is None else reports
        self.valuations = [] if valuations is None else valuations
        self.fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return "recording"

    def get_latest_fundamentals(self, *, symbol: str, exchange: str, currency: str, country: str) -> ReportedFundamental | None:
        del symbol, exchange, currency, country
        history = self.get_fundamental_history(symbol="TCS", exchange="NSE", currency="INR", country="IN")
        return history[-1] if history else None

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
        del symbol, exchange, currency, country, start, end
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return self.reports

    def get_latest_valuation(self, *, symbol: str, exchange: str, currency: str, country: str) -> ValuationReading | None:
        del symbol, exchange, currency, country
        history = self.get_valuation_history(symbol="TCS", exchange="NSE", currency="INR", country="IN")
        return history[-1] if history else None

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
        del symbol, exchange, currency, country, start, end
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return self.valuations


def _auth(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"fundamentals-{uuid.uuid4().hex}@example.com",
            "password": PASSWORD,
            "full_name": "Fundamentals Tester",
        },
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text


def _db() -> Session:
    override = app.dependency_overrides[get_db]
    return next(override())


def _tcs(db: Session) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == "TCS", Stock.exchange == "NSE"))
    assert stock is not None
    hide_committed_market_rows(db, stock.id)
    return stock


def _report(**overrides: object) -> ReportedFundamental:
    payload: dict[str, object] = {
        "fiscal_period": "FY2026",
        "fiscal_period_type": "annual",
        "period_end": date(2026, 3, 31),
        "filing_date": date(2026, 5, 12),
        "currency": "INR",
        "revenue": Decimal("100.00"),
        "revenue_growth": None,
        "ebitda": None,
        "ebitda_growth": None,
        "operating_profit": Decimal("20.00"),
        "net_income": Decimal("10.00"),
        "profit_growth": None,
        "eps": Decimal("5.0000"),
        "eps_growth": None,
        "book_value_per_share": None,
        "roe": Decimal("15.000000"),
        "roce": None,
        "gross_margin": None,
        "operating_margin": None,
        "net_margin": None,
        "debt_to_equity": None,
        "current_ratio": None,
        "interest_coverage": None,
        "free_cash_flow": None,
        "operating_cash_flow": Decimal("8.00"),
        "provider_retrieved_at": RETRIEVED,
    }
    payload.update(overrides)
    return ReportedFundamental(**payload)  # type: ignore[arg-type]


def _valuation(**overrides: object) -> ValuationReading:
    payload: dict[str, object] = {
        "snapshot_at": datetime(2026, 9, 23, 10, 0, tzinfo=IST),
        "market_price": Decimal("4000.0000"),
        "market_cap": Decimal("1000000.00"),
        "enterprise_value": Decimal("1100000.00"),
        "pe_ratio": Decimal("24.500000"),
        "pb_ratio": None,
        "peg_ratio": None,
        "ev_to_ebitda": None,
        "ev_to_sales": None,
        "dividend_yield": Decimal("1.200000"),
        "currency": "INR",
        "provider_retrieved_at": RETRIEVED,
    }
    payload.update(overrides)
    return ValuationReading(**payload)  # type: ignore[arg-type]


def _use(provider: FundamentalDataProvider, cache: MemoryFundamentalCache | None = None) -> MemoryFundamentalCache:
    store = cache or MemoryFundamentalCache()
    app.dependency_overrides[get_fundamental_data_provider] = lambda: provider
    app.dependency_overrides[get_fundamental_cache] = lambda: store
    return store


def test_normalize_known_aliases_and_rejects_unknown_fields() -> None:
    report = normalize_report(
        {
            "fiscal_period": "FY2026",
            "fiscal_period_type": "annual",
            "period_end": "2026-03-31",
            "filing_date": "2026-05-12",
            "currency": "inr",
            "sales": "100.00",
            "profit": "10.00",
            "eps_basic": "5",
            "return_on_equity": "15",
            "return_on_capital_employed": "18",
            "debt_equity": "0.4",
            "provider_retrieved_at": "2026-05-12T04:30:00Z",
        }
    )
    assert report.revenue == Decimal("100.00")
    assert report.net_income == Decimal("10.00")
    assert report.eps == Decimal("5.0000")
    assert report.roe == Decimal("15.000000")
    assert report.currency == "INR"
    try:
        normalize_report({"fiscal_period": "FY2026", "surprise": "1"})
    except FundamentalDataError as exc:
        assert exc.code == "malformed"
    else:
        raise AssertionError("unknown field was accepted")
    try:
        normalize_valuation({"snapshot_at": "2026-09-23T10:00:00+05:30", "pe_ratio": "nope", "currency": "INR", "provider_retrieved_at": "2026-09-23T10:00:00+05:30"})
    except FundamentalDataError as exc:
        assert exc.code == "malformed"
    else:
        raise AssertionError("malformed ratio was accepted")


def test_unconfigured_and_placeholder_do_not_invent_values() -> None:
    provider = UnconfiguredFundamentalDataProvider()
    try:
        provider.get_fundamental_history(symbol="TCS", exchange="NSE", currency="INR", country="IN")
    except FundamentalDataError as exc:
        assert exc.code == "not_configured"
    else:
        raise AssertionError("unconfigured provider returned data")
    placeholder = IndianFundamentalDataProvider("named-adapter")
    try:
        placeholder.get_latest_valuation(symbol="TCS", exchange="NSE", currency="INR", country="IN")
    except FundamentalDataError as exc:
        assert exc.code == "not_configured"
    else:
        raise AssertionError("placeholder returned a valuation")
    try:
        provider.get_valuation_history(symbol="TCS", exchange="NASDAQ", currency="USD", country="US")
    except FundamentalDataError as exc:
        assert exc.code == "unsupported_exchange"
    else:
        raise AssertionError("non-Indian listing was accepted")


def test_growth_margin_and_missing_inputs() -> None:
    assert growth_percent(Decimal("110"), Decimal("100")) == Decimal("10.000000")
    assert growth_percent(Decimal("-50"), Decimal("-100")) == Decimal("-50.000000")
    assert growth_percent(Decimal("10"), Decimal("0")) is None
    assert growth_percent(None, Decimal("10")) is None
    assert margin_percent(Decimal("10"), Decimal("100")) == Decimal("10.000000")
    assert margin_percent(Decimal("10"), Decimal("0")) is None
    assert margin_percent(Decimal("10"), Decimal("-5")) is None
    assert margin_percent(None, Decimal("10")) is None
    assert cagr_percent(Decimal("100"), Decimal("121"), 2) == Decimal("10.000000")
    assert cagr_percent(Decimal("0"), Decimal("121"), 2) is None
    assert cagr_percent(Decimal("-10"), Decimal("121"), 2) is None


def test_sync_upserts_history_and_keeps_existing_values(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    first = _report()
    earlier = _report(
        fiscal_period="FY2025",
        period_end=date(2025, 3, 31),
        filing_date=date(2025, 5, 12),
        revenue=Decimal("80.00"),
        net_income=Decimal("8.00"),
        operating_profit=None,
        operating_cash_flow=None,
        roe=None,
        eps=None,
    )
    provider = RecordingProvider(reports=[first, earlier])
    _use(provider)
    response = client.get(f"/api/stocks/{stock.id}/fundamentals")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["revenue"] == "100.00"
    assert body["data"]["revenue_growth"] == "25.000000"
    assert body["data"]["net_margin"] == "10.000000"
    assert body["data"]["cfo_to_net_profit"] == "0.800000"
    assert body["period"]["filing_date"] == "2026-05-12"
    assert body["metadata"]["currency"] == "INR"
    assert body["metadata"]["is_available"] is True
    assert "api_key" not in response.text.lower()
    count = db.scalar(select(func.count()).select_from(Fundamental).where(Fundamental.stock_id == stock.id))
    assert count == 2
    provider.reports = [_report(revenue=None, net_income=Decimal("12.00"), operating_profit=None, operating_cash_flow=None, roe=None, eps=None)]
    provider.calls = 0
    app.dependency_overrides[get_fundamental_cache] = lambda: MemoryFundamentalCache()
    again = client.get(f"/api/stocks/{stock.id}/fundamentals")
    assert again.status_code == 200, again.text
    assert again.json()["data"]["revenue"] == "100.00"
    assert again.json()["data"]["net_income"] == "12.00"
    stored = db.scalar(select(func.count()).select_from(Fundamental).where(Fundamental.stock_id == stock.id))
    assert stored == 2


def test_valuation_snapshot_and_cache(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider(valuations=[_valuation()])
    cache = _use(provider)
    response = client.get(f"/api/stocks/{stock.id}/valuation")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pe_ratio"] == "24.500000"
    assert response.json()["data"]["market_cap"] == "1000000.00"
    assert response.json()["metadata"]["source"] == "recording"
    db.query(ValuationSnapshot).filter(ValuationSnapshot.stock_id == stock.id).delete()
    db.commit()
    cached = client.get(f"/api/stocks/{stock.id}/valuation")
    assert cached.status_code == 200
    assert cached.json()["data"]["pe_ratio"] == "24.500000"
    assert provider.calls == 1
    assert cache.get_valuation(f"valuation:{stock.id}:latest") is not None


def test_history_pagination_and_duplicate_snapshot(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    provider = RecordingProvider(
        reports=[
            _report(fiscal_period="FY2025", period_end=date(2025, 3, 31), filing_date=date(2025, 5, 12)),
            _report(),
        ],
        valuations=[_valuation(), _valuation()],
    )
    _use(provider)
    history = client.get(f"/api/stocks/{stock.id}/fundamentals/history", params={"limit": 1, "period": "annual"})
    assert history.status_code == 200, history.text
    payload = history.json()
    assert payload["total"] == 2
    assert len(payload["results"]) == 1
    assert payload["results"][0]["period"]["fiscal_period"] == "FY2025"
    valuation = client.get(f"/api/stocks/{stock.id}/valuation/history")
    assert valuation.status_code == 200, valuation.text
    assert valuation.json()["total"] == 1


def test_missing_stock_unconfigured_and_provider_failures(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    missing = client.get(f"/api/stocks/{uuid.uuid4()}/fundamentals")
    assert missing.status_code == 404
    _use(UnconfiguredFundamentalDataProvider())
    unconfigured = client.get(f"/api/stocks/{stock.id}/fundamentals")
    assert unconfigured.status_code == 503
    assert unconfigured.json()["detail"] == "Fundamental data provider is not configured"
    empty = client.get(f"/api/stocks/{stock.id}/valuation")
    assert empty.status_code == 503
    _use(RecordingProvider(reports=[], valuations=[]))
    no_data = client.get(f"/api/stocks/{stock.id}/fundamentals")
    assert no_data.status_code == 200
    assert no_data.json()["metadata"]["is_available"] is False
    assert no_data.json()["data"]["revenue"] is None
    for fail, status in (
        (TimeoutError(), 502),
        (FundamentalDataError("rate_limited"), 429),
        (FundamentalDataError("malformed"), 502),
        (OSError("down"), 502),
        (FundamentalDataError("unauthorized"), 502),
    ):
        _use(RecordingProvider(fail=fail))
        failed = client.get(f"/api/stocks/{stock.id}/valuation")
        assert failed.status_code == status, fail
        assert "down" not in failed.text
        assert "api_key" not in failed.text.lower()


def test_sector_comparison_without_a_seeded_benchmark(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    _use(RecordingProvider(reports=[_report()], valuations=[_valuation()]))
    client.get(f"/api/stocks/{stock.id}/fundamentals")
    client.get(f"/api/stocks/{stock.id}/valuation")
    before = client.get(f"/api/stocks/{stock.id}/sector-comparison")
    assert before.status_code == 200, before.text
    assert before.json()["benchmark_available"] is False
    assert all(item["benchmark_value"] is None for item in before.json()["metrics"])
    db.add(
        SectorBenchmark(
            sector=stock.sector or "Information Technology",
            country=stock.country,
            calculation_date=date(2026, 9, 1),
            pe_ratio=Decimal("20.000000"),
            roe=Decimal("12.000000"),
            currency="INR",
            source="test-source",
            methodology="stored row",
        )
    )
    db.commit()
    compared = client.get(f"/api/stocks/{stock.id}/sector-comparison")
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["benchmark_available"] is True
    assert body["source"] == "test-source"
    pe = next(item for item in body["metrics"] if item["metric"] == "pe_ratio")
    assert pe["stock_value"] == "24.500000"
    assert pe["benchmark_value"] == "20.000000"
    assert pe["difference"] == "4.500000"
    assert "buy" not in compared.text.lower()


def test_quarterly_report_borrows_annual_balance_sheet(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    annual = _report(debt_to_equity=Decimal("0.200000"), current_ratio=Decimal("2.100000"))
    quarter = _report(
        fiscal_period="Q1FY2027",
        fiscal_period_type="quarterly",
        period_end=date(2026, 6, 30),
        filing_date=None,
        revenue=Decimal("40.00"),
        net_income=Decimal("8.00"),
        operating_profit=Decimal("12.00"),
        operating_cash_flow=None,
        roe=None,
        debt_to_equity=None,
        current_ratio=None,
        eps=Decimal("2.0000"),
    )
    _use(RecordingProvider(reports=[annual, quarter]))
    response = client.get(f"/api/stocks/{stock.id}/fundamentals")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"]["fiscal_period"] == "Q1FY2027"
    assert body["data"]["revenue"] == "40.00"
    assert body["data"]["debt_to_equity"] == "0.200000"
    assert body["data"]["current_ratio"] == "2.100000"
    assert body["data"]["cfo_to_net_profit"] == "0.800000"
    assert body["metadata"]["supplemented_from_period"] == "FY2026"


def test_fundamentals_require_a_session(client: TestClient) -> None:
    response = client.get(f"/api/stocks/{uuid.uuid4()}/fundamentals")
    assert response.status_code == 401
