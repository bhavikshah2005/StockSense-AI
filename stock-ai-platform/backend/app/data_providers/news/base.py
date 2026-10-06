from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProviderArticle:
    """Normalized headline. Publication time is the publisher's time, or None if the feed omitted it."""

    provider: str
    provider_article_id: str | None
    title: str
    summary: str | None
    url: str
    source: str
    author: str | None
    published_at: datetime | None
    language: str | None


@dataclass(frozen=True)
class FetchResult:
    articles: list[ProviderArticle]
    errors: list[str]


class NewsProvider(ABC):
    """Indian market headlines. Routes do not call a vendor directly."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier."""

    @property
    def configured(self) -> bool:
        return True

    @abstractmethod
    def fetch(self) -> FetchResult:
        """Return recent articles. One feed failure is recorded without dropping the others."""
