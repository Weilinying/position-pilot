"""News Schema 与结果状态测试。"""

from datetime import UTC, datetime, timedelta

import pytest

from position_pilot.domain.news import (
    NO_NEWS_FOUND_MESSAGE,
    InvalidNews,
    NewsArticle,
    NewsResult,
    NewsStatus,
    RecentNews,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def article(
    article_id: str = "article-1",
    *,
    updated_at: datetime = NOW,
    symbols: tuple[str, ...] = ("GOOG",),
) -> NewsArticle:
    """构造满足 Schema 的最小新闻事实。"""

    return NewsArticle(
        article_id=article_id,
        headline="Google reports results",
        summary="A provider supplied summary.",
        author="Reporter",
        url=f"https://news.example.test/articles/{article_id}",
        source="Example News",
        symbols=symbols,
        created_at=NOW - timedelta(hours=1),
        updated_at=updated_at,
    )


def test_news_article_normalizes_symbols_and_utc_timestamps() -> None:
    """Article 应保存规范化标的和可比较的 UTC 时间。"""

    value = article(symbols=(" goog ", "msft"))

    assert value.symbols == ("GOOG", "MSFT")
    assert value.source == "Example News"
    assert value.updated_at == NOW


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("article_id", " ", "article_id"),
        ("headline", " ", "headline"),
        ("summary", " ", "summary"),
        ("author", " ", "author"),
        ("url", "ftp://news.example.test/item", "HTTP"),
        ("url", "https://news.example.test/a b", "空白"),
        ("source", " ", "source"),
        ("symbols", ("GOOG", "goog"), "重复"),
        ("symbols", ("not/a/ticker",), "无效"),
    ],
)
def test_news_article_rejects_invalid_text_url_and_symbols(
    field: str,
    value: str | tuple[str, ...],
    match: str,
) -> None:
    """外部文章必须在 Domain 边界完成严格校验。"""

    arguments: dict[str, object] = {
        "article_id": "article-1",
        "headline": "Google reports results",
        "summary": "A provider supplied summary.",
        "author": "Reporter",
        "url": "https://news.example.test/articles/article-1",
        "source": "Example News",
        "symbols": ("GOOG",),
        "created_at": NOW - timedelta(hours=1),
        "updated_at": NOW,
    }
    arguments[field] = value

    with pytest.raises(InvalidNews, match=match):
        NewsArticle(**arguments)  # type: ignore[arg-type]


def test_news_article_rejects_naive_or_backdated_update_time() -> None:
    """新闻生命周期时间必须带时区且不能倒流。"""

    with pytest.raises(InvalidNews, match="created_at"):
        NewsArticle(
            article_id="article-1",
            headline="Headline",
            summary=None,
            author=None,
            url="https://news.example.test/article-1",
            source="Example",
            symbols=("GOOG",),
            created_at=datetime(2026, 8, 25, 11, 0),
            updated_at=NOW,
        )
    with pytest.raises(InvalidNews, match="不得早于"):
        article(updated_at=NOW - timedelta(hours=2))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("article_id", "x" * 201),
        ("headline", "x" * 501),
        ("summary", "x" * 2_001),
        ("author", "x" * 201),
        ("source", "x" * 201),
    ],
)
def test_news_article_bounds_all_external_text(field: str, value: str) -> None:
    """五篇报道进入 LLM 前，每个外部文本字段都必须有明确上限。"""

    arguments: dict[str, object] = {
        "article_id": "article-1",
        "headline": "Headline",
        "summary": "Summary",
        "author": "Reporter",
        "url": "https://news.example.test/article-1",
        "source": "Example",
        "symbols": ("GOOG",),
        "created_at": NOW - timedelta(hours=1),
        "updated_at": NOW,
    }
    arguments[field] = value

    with pytest.raises(InvalidNews, match="长度"):
        NewsArticle(**arguments)  # type: ignore[arg-type]


def test_recent_news_normalizes_exact_duplicates_and_stable_order() -> None:
    """集合应只含目标标的文章，并主动完成稳定排序和精确去重。"""

    newer = article("z", updated_at=NOW)
    older = article("a", updated_at=NOW - timedelta(minutes=1))
    result = RecentNews(
        ticker=" goog ",
        articles=(older, newer, newer),
        provider="Alpaca",
        fetched_at=NOW,
    )

    assert result.ticker == "GOOG"
    assert [item.article_id for item in result.articles] == ["z", "a"]

    same_time = RecentNews(
        "GOOG",
        (article("a", updated_at=NOW), article("z", updated_at=NOW)),
        "Alpaca",
        NOW,
    )
    assert [item.article_id for item in same_time.articles] == ["a", "z"]

    with pytest.raises(InvalidNews, match="冲突内容"):
        RecentNews(
            "GOOG", (newer, article("z", updated_at=NOW - timedelta(minutes=1))), "Alpaca", NOW
        )
    with pytest.raises(InvalidNews, match="查询 ticker"):
        RecentNews("GOOG", (article(symbols=("MSFT",)),), "Alpaca", NOW)


def test_recent_news_rejects_fetched_time_before_latest_reporting_update() -> None:
    """获取时间不得早于 Provider 声称的最新文章更新时间。"""

    with pytest.raises(InvalidNews, match="fetched_at"):
        RecentNews(
            "GOOG",
            (article(updated_at=NOW),),
            "Alpaca",
            NOW - timedelta(seconds=1),
        )


def test_news_result_enforces_success_failure_and_no_news_semantics() -> None:
    """空新闻不得被表述成没有相关新闻或驱动因素。"""

    result: NewsResult[object] = NewsResult.failure(
        NewsStatus.NO_NEWS_FOUND,
        "Provider 原始空结果",
    )

    assert result.message is not None
    assert NO_NEWS_FOUND_MESSAGE in result.message
    with pytest.raises(InvalidNews, match="不能包含 data"):
        NewsResult(NewsStatus.RATE_LIMITED, "invented", "限流")
    with pytest.raises(InvalidNews, match="不代表不存在"):
        NewsResult(NewsStatus.NO_NEWS_FOUND, None, "没有新闻")
    with pytest.raises(InvalidNews, match="failure"):
        NewsResult.failure(NewsStatus.OK, "错误")
