import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.data_providers.news.base import FetchResult, ProviderArticle
from app.data_providers.news.errors import NewsProviderError
from app.data_providers.news.rss import RssNewsProvider, parse_feed, plain_text
from app.main import app
from app.models import NewsArticle, Stock
from app.news.ingest import LOCK_KEY, ingest
from app.news.matching import StockName, match_stocks
from app.news.sentiment import classify
from tests.isolation import hide_committed_market_rows

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"
RSS = """<?xml version="1.0"?>
<rss><channel>
<item>
  <title><![CDATA[TCS <b>profit</b> rises after a strong quarter]]></title>
  <link>https://example.com/tcs?utm_source=feed</link>
  <guid>fixture-tcs-1</guid>
  <pubDate>Wed, 24 Sep 2026 09:00:00 +0530</pubDate>
  <description>Test fixture, not a live headline. Profit rises.</description>
</item>
<item>
  <title>Broken</title>
</item>
</channel></rss>"""


class FixtureProvider:
    name = "rss"
    configured = True

    def __init__(self, articles: list[ProviderArticle], errors: list[str] | None = None) -> None:
        self.articles = articles
        self.errors = errors or []

    def fetch(self) -> FetchResult:
        return FetchResult(self.articles, self.errors)


def _auth(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": f"news-{uuid.uuid4().hex}@example.com", "password": PASSWORD, "full_name": "News Tester"},
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


def _article(title: str, url: str, summary: str | None = None) -> ProviderArticle:
    return ProviderArticle(
        provider="rss",
        provider_article_id=url,
        title=title,
        summary=summary,
        url=url,
        source="example.com",
        author=None,
        published_at=datetime.now(UTC) - timedelta(hours=1),
        language="en",
    )


def test_rss_parser_strips_markup_and_rejects_malformed_feeds() -> None:
    parsed = parse_feed(RSS, source_name="example.com")
    assert len(parsed) == 1
    assert "<" not in parsed[0].title
    assert parsed[0].url == "https://example.com/tcs"
    assert parsed[0].published_at is not None
    assert plain_text("<script>alert(1)</script> Profit rises") == "alert(1) Profit rises"
    try:
        parse_feed("<html>not a feed", source_name="example.com")
    except NewsProviderError as exc:
        assert exc.code == "malformed"
    else:
        raise AssertionError("malformed feed was accepted")


def test_rss_provider_reports_timeout_and_rate_limit() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    timed = RssNewsProvider(["https://feeds.example/news.xml"], transport=httpx.MockTransport(timeout))
    result = timed.fetch()
    assert result.articles == []
    assert result.errors == ["feeds.example: timeout"]

    limited = RssNewsProvider(
        ["https://feeds.example/news.xml"],
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, text="slow down")),
    )
    assert limited.fetch().errors == ["feeds.example: rate_limited"]


def test_matcher_requires_a_real_symbol_or_distinctive_name() -> None:
    stock_id = uuid.uuid4()
    other_id = uuid.uuid4()
    stocks = [
        StockName(stock_id, "TCS", "Tata Consultancy Services Limited"),
        StockName(other_id, "RELIANCE", "Reliance Industries Limited"),
    ]
    linked = {match.stock_id for match in match_stocks("Tata Consultancy Services profit rises today", None, stocks)}
    assert linked == {stock_id}
    assert match_stocks("IT services expand across India today", None, stocks) == []
    power = StockName(uuid.uuid4(), "RPOWER", "Reliance Power Limited")
    headline = "Reliance Power profit rises after a strong quarter"
    power_ids = {match.stock_id for match in match_stocks(headline, None, [*stocks, power])}
    assert other_id not in power_ids
    assert power.id in power_ids


def test_sentiment_stays_uncertain_for_short_or_mixed_text() -> None:
    assert classify("TCS", None).label == "uncertain"
    mixed = classify("TCS profit rises but fraud probe continues today", None)
    assert mixed.label == "uncertain"
    assert "profit" in mixed.explanation
    assert "fraud" in mixed.explanation
    assert classify("TCS profit rises after a strong quarter", None).label == "positive"


def test_ingest_deduplicates_and_links_tcs(client: TestClient) -> None:
    _auth(client)
    db = _db()
    stock = _tcs(db)
    provider = FixtureProvider(
        [
            _article("TCS profit rises after a strong quarter", "https://example.com/tcs-profit"),
            _article("Untitled move", "https://example.com/no-time", None),
        ]
    )
    provider.articles[1] = ProviderArticle(
        provider="rss",
        provider_article_id="missing-time",
        title="No publication time",
        summary="Test fixture",
        url="https://example.com/no-time",
        source="example.com",
        author=None,
        published_at=None,
        language=None,
    )
    first = ingest(db, provider)
    assert first["status"] == "success"
    assert first["stored"] == 1
    second = ingest(db, provider)
    assert second["stored"] == 0
    assert db.scalar(select(func.count()).select_from(NewsArticle)) == 1
    listed = client.get("/api/news?sentiment=positive")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert str(stock.id) in {item["stock_id"] for item in body["results"][0]["stocks"]}
    assert body["results"][0]["ingested_at"] != body["results"][0]["published_at"]
    stock_news = client.get(f"/api/news?stock_id={stock.id}")
    assert stock_news.json()["total"] == 1
    page = client.get("/api/news?limit=1&offset=0")
    assert page.json()["limit"] == 1
    detail = client.get(f"/api/news/{body['results'][0]['id']}/sentiment")
    assert detail.status_code == 200
    assert detail.json()["label"] == "positive"
    assert "not a forecast" in detail.json()["methodology"]


def test_status_is_unconfigured_without_feeds(client: TestClient) -> None:
    _auth(client)
    status = client.get("/api/news/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False
    assert status.json()["provider"] == "unconfigured"
    empty = client.get("/api/news")
    assert empty.status_code == 200
    assert empty.json()["results"] == []


def test_second_ingest_skips_while_the_lock_is_held(client: TestClient) -> None:
    _auth(client)
    other = engine.connect()
    try:
        assert other.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar() is True
        assert ingest(_db(), FixtureProvider([]))["status"] == "skipped"
    finally:
        other.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        other.close()
