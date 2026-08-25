"""Provider-neutral News Schema 与确定性校验。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import normalize_ticker

MAX_ARTICLE_ID_LENGTH = 200
MAX_HEADLINE_LENGTH = 500
MAX_SUMMARY_LENGTH = 2_000
MAX_AUTHOR_LENGTH = 200
MAX_URL_LENGTH = 2_048
MAX_SOURCE_LENGTH = 200
MAX_SYMBOLS_PER_ARTICLE = 50
NO_NEWS_FOUND_MESSAGE = (
    "当前 Provider 在指定 ticker/窗口未返回新闻；不代表不存在相关新闻、事件或驱动因素。"
)


class InvalidNews(ValueError):
    """News Schema 包含无效或互相冲突的事实。"""


class NewsStatus(StrEnum):
    """Provider 调用的稳定新闻结果状态。"""

    OK = "OK"
    NO_NEWS_FOUND = "NO_NEWS_FOUND"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"


def normalize_news_timestamp(value: datetime, *, field_name: str) -> datetime:
    """要求新闻时间包含时区并统一为 UTC。"""

    if not isinstance(value, datetime):
        raise InvalidNews(f"{field_name} 必须是 datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidNews(f"{field_name} 必须包含时区")
    return value.astimezone(UTC)


def _normalize_required_text(value: str, *, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidNews(f"{field_name} 必须是字符串")
    normalized = value.strip()
    if not normalized:
        raise InvalidNews(f"{field_name} 不能为空")
    if len(normalized) > max_length:
        raise InvalidNews(f"{field_name} 长度不得超过 {max_length}")
    return normalized


def _normalize_optional_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    return _normalize_required_text(value, field_name=field_name, max_length=max_length)


def _normalize_url(value: str) -> str:
    normalized = _normalize_required_text(value, field_name="url", max_length=MAX_URL_LENGTH)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidNews("url 必须是带 host 的 HTTP 或 HTTPS URL")
    if any(character.isspace() for character in normalized):
        raise InvalidNews("url 不得包含空白字符")
    return normalized


def _normalize_symbols(value: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise InvalidNews("symbols 必须是非空 tuple")
    if len(value) > MAX_SYMBOLS_PER_ARTICLE:
        raise InvalidNews(f"symbols 不得超过 {MAX_SYMBOLS_PER_ARTICLE} 个")
    try:
        normalized = tuple(normalize_ticker(symbol) for symbol in value)
    except (InvalidPortfolioValue, AttributeError) as error:
        raise InvalidNews("symbols 包含无效 ticker") from error
    if len(set(normalized)) != len(normalized):
        raise InvalidNews("symbols 不得包含重复 ticker")
    return normalized


@dataclass(frozen=True, slots=True)
class NewsArticle:
    """一篇带来源、标的和时间边界的不可变新闻事实。"""

    article_id: str
    headline: str
    summary: str | None
    author: str | None
    url: str
    source: str
    symbols: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "article_id",
            _normalize_required_text(
                self.article_id,
                field_name="article_id",
                max_length=MAX_ARTICLE_ID_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "headline",
            _normalize_required_text(
                self.headline,
                field_name="headline",
                max_length=MAX_HEADLINE_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "summary",
            _normalize_optional_text(
                self.summary,
                field_name="summary",
                max_length=MAX_SUMMARY_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "author",
            _normalize_optional_text(
                self.author,
                field_name="author",
                max_length=MAX_AUTHOR_LENGTH,
            ),
        )
        object.__setattr__(self, "url", _normalize_url(self.url))
        object.__setattr__(
            self,
            "source",
            _normalize_required_text(
                self.source,
                field_name="source",
                max_length=MAX_SOURCE_LENGTH,
            ),
        )
        object.__setattr__(self, "symbols", _normalize_symbols(self.symbols))
        object.__setattr__(
            self,
            "created_at",
            normalize_news_timestamp(self.created_at, field_name="created_at"),
        )
        object.__setattr__(
            self,
            "updated_at",
            normalize_news_timestamp(self.updated_at, field_name="updated_at"),
        )
        if self.updated_at < self.created_at:
            raise InvalidNews("updated_at 不得早于 created_at")


@dataclass(frozen=True, slots=True)
class RecentNews:
    """指定标的近期新闻的不可变、稳定排序集合。"""

    ticker: str
    articles: tuple[NewsArticle, ...]
    provider: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        try:
            normalized_ticker = normalize_ticker(self.ticker)
        except (InvalidPortfolioValue, AttributeError) as error:
            raise InvalidNews("ticker 格式无效") from error
        object.__setattr__(self, "ticker", normalized_ticker)
        if not isinstance(self.articles, tuple) or not self.articles:
            raise InvalidNews("articles 必须是非空 tuple")
        if any(not isinstance(article, NewsArticle) for article in self.articles):
            raise InvalidNews("articles 必须只包含 NewsArticle")
        if any(self.ticker not in article.symbols for article in self.articles):
            raise InvalidNews("每篇文章必须包含查询 ticker")
        unique_by_id: dict[str, NewsArticle] = {}
        for article in self.articles:
            existing = unique_by_id.get(article.article_id)
            if existing is not None and existing != article:
                raise InvalidNews("相同 article_id 不得包含冲突内容")
            unique_by_id[article.article_id] = article
        by_article_id = sorted(unique_by_id.values(), key=lambda article: article.article_id)
        ordered_articles = tuple(
            sorted(by_article_id, key=lambda article: article.updated_at, reverse=True)
        )
        object.__setattr__(self, "articles", ordered_articles)
        object.__setattr__(
            self,
            "provider",
            _normalize_required_text(
                self.provider,
                field_name="provider",
                max_length=MAX_SOURCE_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "fetched_at",
            normalize_news_timestamp(self.fetched_at, field_name="fetched_at"),
        )
        if self.fetched_at < self.articles[0].updated_at:
            raise InvalidNews("fetched_at 不得早于最新文章的 updated_at")


@dataclass(frozen=True, slots=True)
class NewsResult[T]:
    """成功新闻与明确失败状态的统一结构。"""

    status: NewsStatus
    data: T | None
    message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, NewsStatus):
            raise InvalidNews("status 无效")
        if self.status is NewsStatus.OK:
            if self.data is None or self.message is not None:
                raise InvalidNews("OK result 必须包含 data 且不能包含 message")
            return
        if self.data is not None:
            raise InvalidNews("Failure result 不能包含 data")
        if not isinstance(self.message, str) or not self.message.strip():
            raise InvalidNews("Failure result 必须包含 message")
        if self.status is NewsStatus.NO_NEWS_FOUND and NO_NEWS_FOUND_MESSAGE not in self.message:
            raise InvalidNews("NO_NEWS_FOUND 必须说明不代表不存在相关新闻、事件或驱动因素")

    @classmethod
    def success(cls, data: T) -> "NewsResult[T]":
        """创建成功结果。"""

        return cls(status=NewsStatus.OK, data=data, message=None)

    @classmethod
    def failure(
        cls,
        status: NewsStatus,
        message: str = "",
    ) -> "NewsResult[T]":
        """创建不携带伪造新闻事实的失败结果。"""

        if status is NewsStatus.OK:
            raise InvalidNews("failure 不能使用 OK status")
        if status is NewsStatus.NO_NEWS_FOUND:
            detail = message.strip()
            message = f"{NO_NEWS_FOUND_MESSAGE} {detail}".strip()
        return cls(status=status, data=None, message=message)
