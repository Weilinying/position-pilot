"""News Application Service 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from position_pilot.application.news_service import NewsQuery, NewsService
from position_pilot.domain.news import NewsResult, NewsStatus, RecentNews

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 20, tzinfo=UTC)


@dataclass(slots=True)
class FakeNewsProvider:
    """记录 Application 向 Provider 发出的规范化请求。"""

    queries: list[NewsQuery] = field(default_factory=list)

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        self.queries.append(query)
        return NewsResult.failure(NewsStatus.NO_NEWS_FOUND, "测试无文章")


def test_service_normalizes_ticker_before_provider_call() -> None:
    """Provider 只能收到 Portfolio 已批准格式的 Ticker。"""

    provider = FakeNewsProvider()
    service = NewsService(provider)

    result = service.get_recent_news(NewsQuery(" goog ", START, END, 12))

    assert result.status is NewsStatus.NO_NEWS_FOUND
    assert provider.queries == [NewsQuery("GOOG", START, END, 12)]


@pytest.mark.parametrize(
    "query",
    [
        NewsQuery("not/a/ticker", START, END),
        NewsQuery("GOOG", END, START),
        NewsQuery("GOOG", datetime(2026, 8, 1), END),
        NewsQuery("GOOG", START, datetime(2026, 8, 20)),
        NewsQuery("GOOG", START, END, 0),
        NewsQuery("GOOG", START, END, 51),
        NewsQuery("GOOG", START, END, True),
    ],
)
def test_service_rejects_invalid_queries_without_provider_call(query: NewsQuery) -> None:
    """无效输入不得消耗 Provider 配额。"""

    provider = FakeNewsProvider()
    service = NewsService(provider)

    result = service.get_recent_news(query)

    assert result.status in {NewsStatus.INVALID_SYMBOL, NewsStatus.INVALID_REQUEST}
    assert provider.queries == []


def test_service_rejects_non_query_runtime_value_without_provider_call() -> None:
    """稳定边界不能只依赖调用方的静态 Type Hint。"""

    provider = FakeNewsProvider()
    service = NewsService(provider)

    result = service.get_recent_news("GOOG")  # type: ignore[arg-type]

    assert result.status is NewsStatus.INVALID_REQUEST
    assert provider.queries == []
