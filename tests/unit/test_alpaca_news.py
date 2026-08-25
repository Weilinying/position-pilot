"""Alpaca News Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from position_pilot.application.news_service import NewsQuery
from position_pilot.domain.news import NewsStatus
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailureKind,
    HttpTransportUnavailable,
    JsonHttpResponse,
)
from position_pilot.integrations.alpaca_news import AlpacaNewsProvider

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
START = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
END = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    """记录 Adapter 发出的不透明 HTTP 请求。"""

    url: str
    headers: dict[str, str]
    timeout_seconds: float


@dataclass(slots=True)
class FakeJsonTransport:
    """按顺序返回固定 JSON Response。"""

    responses: list[JsonHttpResponse]
    requests: list[RecordedRequest] = field(default_factory=list)

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        self.requests.append(RecordedRequest(url, dict(headers), timeout_seconds))
        return self.responses.pop(0)


class UnavailableTransport:
    """模拟不会暴露底层异常文本的连接失败。"""

    def __init__(self, kind: HttpTransportFailureKind) -> None:
        self._kind = kind

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        del url, headers, timeout_seconds
        try:
            raise RuntimeError("test-secret must not leak")
        except RuntimeError as error:
            raise HttpTransportUnavailable(self._kind) from error


def make_provider(
    transport: FakeJsonTransport | UnavailableTransport,
    *,
    api_key_id: str | None = "test-key",
    api_secret_key: str | None = "test-secret",
) -> AlpacaNewsProvider:
    """创建固定 Clock 与 Fake Transport 的 Provider。"""

    return AlpacaNewsProvider(
        api_key_id=api_key_id,
        api_secret_key=api_secret_key,
        base_url="https://data.example.test",
        timeout_seconds=3,
        transport=transport,
        clock=lambda: NOW,
    )


def query(ticker: str = "GOOG") -> NewsQuery:
    """生成经 Application Service 预期校验的固定查询。"""

    return NewsQuery(ticker=ticker, start=START, end=END, limit=5)


def article(**overrides: object) -> dict[str, object]:
    """生成包含 Alpaca News 最小字段的固定文章。"""

    value: dict[str, object] = {
        "id": "news-1",
        "headline": "Alphabet update",
        "summary": "A short provider summary.",
        "author": "Reporter",
        "url": "https://news.example.test/articles/1",
        "source": "Example News",
        "symbols": ["GOOG"],
        "created_at": "2026-08-24T10:00:00Z",
        "updated_at": "2026-08-24T10:30:00Z",
        "content": "This must never be parsed into the domain model.",
    }
    value.update(overrides)
    return value


def test_requests_fixed_news_endpoint_without_content_and_parses_article() -> None:
    """请求必须包含固定查询参数，且结果只保留经批准文章字段。"""

    transport = FakeJsonTransport([JsonHttpResponse(200, {"news": [article()]})])

    result = make_provider(transport).get_recent_news(query())

    assert result.status is NewsStatus.OK
    assert result.data is not None
    assert result.data.ticker == "GOOG"
    assert result.data.provider == "ALPACA"
    assert result.data.fetched_at == NOW
    assert len(result.data.articles) == 1
    parsed = result.data.articles[0]
    assert parsed.article_id == "news-1"
    assert parsed.headline == "Alphabet update"
    assert parsed.source == "EXAMPLE NEWS"
    assert parsed.symbols == ("GOOG",)
    assert parsed.created_at.tzinfo is UTC
    request = transport.requests[0]
    assert request.url.startswith("https://data.example.test/v1beta1/news?")
    assert "symbols=GOOG" in request.url
    assert "start=2026-08-20T12%3A00%3A00Z" in request.url
    assert "end=2026-08-25T12%3A00%3A00Z" in request.url
    assert "sort=desc" in request.url
    assert "limit=5" in request.url
    assert "include_content=false" in request.url
    assert request.headers["APCA-API-KEY-ID"] == "test-key"
    assert request.headers["APCA-API-SECRET-KEY"] == "test-secret"


def test_empty_news_list_is_normal_no_news_found() -> None:
    """空列表是可预期结果，不能伪装为 Provider Failure。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"news": []})])
    ).get_recent_news(query())

    assert result.status is NewsStatus.NO_NEWS_FOUND
    assert result.data is None


def test_normalizes_numeric_alpaca_article_id_to_domain_string() -> None:
    """Alpaca 的 JSON 数字文章 ID 必须保留为稳定的领域字符串。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"news": [article(id=123456)]})])
    ).get_recent_news(query())

    assert result.status is NewsStatus.OK
    assert result.data is not None
    assert result.data.articles[0].article_id == "123456"


def test_normalizes_blank_optional_reporting_text_to_none() -> None:
    """Alpaca 允许空摘要；可选空文本不应被误报为非法 Provider Response。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"news": [article(summary="", author="  ")]})])
    ).get_recent_news(query())

    assert result.status is NewsStatus.OK
    assert result.data is not None
    assert result.data.articles[0].summary is None
    assert result.data.articles[0].author is None


def test_filters_articles_not_explicitly_attributed_to_query_ticker() -> None:
    """Provider 混入其他标的文章时只能保留 symbols 包含查询 ticker 的记录。"""

    result = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(
                    200,
                    {"news": [article(id="other", symbols=["MSFT"]), article()]},
                )
            ]
        )
    ).get_recent_news(query())

    assert result.status is NewsStatus.OK
    assert result.data is not None
    assert tuple(item.article_id for item in result.data.articles) == ("news-1",)


def test_nonmatching_news_is_no_news_found() -> None:
    """非空响应但没有查询标的归因也必须明确表示无新闻。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"news": [article(symbols=["MSFT"])]})])
    ).get_recent_news(query())

    assert result.status is NewsStatus.NO_NEWS_FOUND
    assert result.data is None


def test_rejects_articles_outside_requested_window_or_above_limit() -> None:
    """Provider Response 也必须服从 Application 固定的时间与条数边界。"""

    outside = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(
                    200,
                    {"news": [article(updated_at="2026-08-19T11:59:59Z")]},
                )
            ]
        )
    ).get_recent_news(query())
    too_many = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(
                    200,
                    {"news": [article(id=index) for index in range(1, 7)]},
                )
            ]
        )
    ).get_recent_news(query())

    assert outside.status is NewsStatus.INVALID_PROVIDER_RESPONSE
    assert too_many.status is NewsStatus.INVALID_PROVIDER_RESPONSE


def test_missing_credentials_do_not_issue_http_request() -> None:
    """缺失任意凭据必须在 Adapter 边界失败。"""

    transport = FakeJsonTransport([])

    result = make_provider(transport, api_secret_key=None).get_recent_news(query())

    assert result.status is NewsStatus.AUTHENTICATION_FAILED
    assert transport.requests == []


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, NewsStatus.INVALID_REQUEST),
        (401, NewsStatus.AUTHENTICATION_FAILED),
        (403, NewsStatus.AUTHENTICATION_FAILED),
        (404, NewsStatus.INVALID_PROVIDER_RESPONSE),
        (429, NewsStatus.RATE_LIMITED),
        (500, NewsStatus.PROVIDER_UNAVAILABLE),
        (418, NewsStatus.INVALID_PROVIDER_RESPONSE),
    ],
)
def test_maps_http_failures_without_leaking_upstream_payload(
    status_code: int,
    expected: NewsStatus,
) -> None:
    """HTTP 状态使用稳定 NewsStatus，不能向调用方泄露 Provider 文本。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(status_code, {"message": "test-secret leaked"})])
    ).get_recent_news(query())

    assert result.status is expected
    assert result.data is None
    assert result.message is not None
    assert "test-secret" not in result.message


@pytest.mark.parametrize(
    "kind",
    [
        HttpTransportFailureKind.TLS_CERTIFICATE_ERROR,
        HttpTransportFailureKind.TIMEOUT,
        HttpTransportFailureKind.NETWORK_ERROR,
    ],
)
def test_maps_transport_failures_without_leaking_underlying_exception(
    kind: HttpTransportFailureKind,
) -> None:
    """网络层 Failure 与 NO_NEWS_FOUND 保持可区分。"""

    result = make_provider(UnavailableTransport(kind)).get_recent_news(query())

    assert result.status is NewsStatus.PROVIDER_UNAVAILABLE
    assert result.message is not None
    assert "test-secret" not in result.message


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"news": {}},
        {"news": ["not-an-object"]},
        {"news": [article(created_at="2026-08-24T10:00:00")]},
        {"news": [article(updated_at="invalid-time")]},
        {"news": [article(headline="  ")]},
        {"news": [article(symbols=["GOOG", 1])]},
    ],
)
def test_rejects_invalid_provider_payload_or_article_semantics(payload: object) -> None:
    """文章身份、时间、归因和文本缺失时不能静默降级为事实。"""

    result = make_provider(FakeJsonTransport([JsonHttpResponse(200, payload)])).get_recent_news(
        query()
    )

    assert result.status is NewsStatus.INVALID_PROVIDER_RESPONSE
    assert result.data is None


def test_rejects_overlong_article_through_domain_validation() -> None:
    """Adapter 必须把领域拒绝的超长外部文本转换为稳定失败状态。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"news": [article(headline="x" * 10_001)]})])
    ).get_recent_news(query())

    assert result.status is NewsStatus.INVALID_PROVIDER_RESPONSE
    assert result.data is None
