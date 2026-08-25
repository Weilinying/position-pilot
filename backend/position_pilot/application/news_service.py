"""News Application Service 与 Provider Contract。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.news import NewsResult, NewsStatus, RecentNews
from position_pilot.domain.portfolio import normalize_ticker


@dataclass(frozen=True, slots=True)
class NewsQuery:
    """近期新闻的 Provider-neutral 输入。"""

    ticker: str
    start: datetime
    end: datetime
    limit: int = 10


class NewsProvider(Protocol):
    """Application 所依赖的最小 News Provider 接口。"""

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]: ...


class NewsService:
    """校验调用方输入并委托单一 News Provider。"""

    def __init__(self, provider: NewsProvider) -> None:
        self._provider = provider

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        """校验固定窗口查询后获取指定标的近期新闻。"""

        if not isinstance(query, NewsQuery):
            return NewsResult.failure(NewsStatus.INVALID_REQUEST, "NewsQuery 类型无效")
        normalized_ticker = self._normalize_ticker(query.ticker)
        if normalized_ticker is None:
            return NewsResult.failure(NewsStatus.INVALID_SYMBOL, "ticker 格式无效")
        if not self._has_timezone(query.start) or not self._has_timezone(query.end):
            return NewsResult.failure(
                NewsStatus.INVALID_REQUEST,
                "start 与 end 必须包含时区",
            )
        if query.start >= query.end:
            return NewsResult.failure(
                NewsStatus.INVALID_REQUEST,
                "start 必须早于 end",
            )
        if (
            isinstance(query.limit, bool)
            or not isinstance(query.limit, int)
            or not 1 <= query.limit <= 50
        ):
            return NewsResult.failure(
                NewsStatus.INVALID_REQUEST,
                "limit 必须在 1 到 50 之间",
            )
        return self._provider.get_recent_news(
            NewsQuery(
                ticker=normalized_ticker,
                start=query.start,
                end=query.end,
                limit=query.limit,
            )
        )

    @staticmethod
    def _normalize_ticker(ticker: str) -> str | None:
        try:
            return normalize_ticker(ticker)
        except (InvalidPortfolioValue, AttributeError):
            return None

    @staticmethod
    def _has_timezone(value: object) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        )
