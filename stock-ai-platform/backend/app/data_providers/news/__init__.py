from app.core.config import settings
from app.data_providers.news.base import FetchResult, NewsProvider, ProviderArticle
from app.data_providers.news.rss import RssNewsProvider


class UnconfiguredNewsProvider(NewsProvider):
    """Used when NEWS_RSS_FEEDS is empty. It does not invent headlines."""

    @property
    def name(self) -> str:
        return "unconfigured"

    @property
    def configured(self) -> bool:
        return False

    def fetch(self) -> FetchResult:
        return FetchResult(articles=[], errors=[])


def get_news_provider() -> NewsProvider:
    feeds = [item.strip() for item in settings.news_rss_feeds.split(",") if item.strip()]
    if settings.news_provider.strip().lower() == "rss" and feeds:
        return RssNewsProvider(
            feeds,
            timeout=float(settings.news_fetch_timeout_seconds),
            limit=settings.news_max_items_per_feed,
        )
    return UnconfiguredNewsProvider()
