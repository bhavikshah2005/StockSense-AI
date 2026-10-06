"""RSS and Atom feeds supplied by the operator.

Only title, link, publisher, time, author, and a short plain-text excerpt are kept.
Full article bodies are not stored. Feed URLs come from NEWS_RSS_FEEDS.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx

from app.data_providers.news.base import FetchResult, ProviderArticle
from app.data_providers.news.errors import NewsProviderError

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_DROP_QUERY = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_EXCERPT_LIMIT = 400


def canonical_url(url: str) -> str | None:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in _DROP_QUERY and not key.lower().startswith("utm_")
    ]
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urlencode(query), ""))


def plain_text(value: str | None, limit: int = _EXCERPT_LIMIT) -> str | None:
    if value is None:
        return None
    text = unescape(_TAG.sub(" ", value))
    text = _SPACE.sub(" ", text).strip()
    if not text:
        return None
    return text[:limit]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ElementTree.Element, name: str) -> str | None:
    for child in list(node):
        if _local(child.tag) == name:
            if child.text and child.text.strip():
                return child.text.strip()
            href = child.attrib.get("href")
            if href:
                return href.strip()
    return None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_feed(xml_text: str, *, source_name: str) -> list[ProviderArticle]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise NewsProviderError("malformed") from exc
    articles: list[ProviderArticle] = []
    nodes = [node for node in root.iter() if _local(node.tag) in {"item", "entry"}]
    for node in nodes:
        title = plain_text(_child_text(node, "title"), limit=300)
        url = canonical_url(_child_text(node, "link") or "")
        if not title or not url:
            continue
        published = _parse_time(_child_text(node, "pubDate") or _child_text(node, "published") or _child_text(node, "updated") or _child_text(node, "date"))
        articles.append(
            ProviderArticle(
                provider="rss",
                provider_article_id=plain_text(_child_text(node, "guid") or _child_text(node, "id"), limit=255),
                title=title,
                summary=plain_text(_child_text(node, "description") or _child_text(node, "summary")),
                url=url,
                source=source_name,
                author=plain_text(_child_text(node, "creator") or _child_text(node, "author"), limit=255),
                published_at=published,
                language=node.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") or root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang"),
            )
        )
    return articles


def feed_label(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or "rss"


class RssNewsProvider:
    """Fetches operator-configured feeds. This is not a website scraper."""

    def __init__(self, feeds: list[str], *, timeout: float = 15, limit: int = 30, transport: httpx.BaseTransport | None = None) -> None:
        self._feeds = feeds
        self._timeout = timeout
        self._limit = limit
        self._transport = transport

    @property
    def name(self) -> str:
        return "rss"

    @property
    def configured(self) -> bool:
        return bool(self._feeds)

    def fetch(self) -> FetchResult:
        articles: list[ProviderArticle] = []
        errors: list[str] = []
        for feed in self._feeds:
            label = feed_label(feed)
            try:
                body = self._get(feed)
                parsed = parse_feed(body, source_name=label)
            except NewsProviderError as exc:
                errors.append(f"{label}: {exc.code}")
                continue
            articles.extend(parsed[: self._limit])
        return FetchResult(articles=articles, errors=errors)

    def _get(self, feed: str) -> str:
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport, headers={"User-Agent": "StockSenseAI/1.0", "Accept": "application/rss+xml, application/atom+xml, application/xml"}) as client:
                response = client.get(feed)
        except httpx.TimeoutException as exc:
            raise NewsProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise NewsProviderError("unavailable") from exc
        if response.status_code == 429:
            raise NewsProviderError("rate_limited")
        if response.status_code >= 400:
            raise NewsProviderError("unavailable")
        content_type = response.headers.get("content-type", "")
        if "html" in content_type and "xml" not in content_type:
            raise NewsProviderError("malformed")
        return response.text
