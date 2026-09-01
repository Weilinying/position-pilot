"""Massive Asset Metadata Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from position_pilot.domain.asset_metadata import (
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetStatus,
    AssetValidationQuery,
)
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailureKind,
    HttpTransportUnavailable,
    JsonHttpResponse,
)
from position_pilot.integrations.massive_asset_metadata import (
    MassiveAssetMetadataProvider,
)


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    """记录请求元数据而不记录 Provider 响应之外的敏感内容。"""

    url: str
    headers: dict[str, str]
    timeout_seconds: float


@dataclass(slots=True)
class FakeJsonTransport:
    """按顺序返回固定 JSON 响应。"""

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
    """模拟底层网络失败且不暴露异常文本。"""

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        try:
            raise RuntimeError("test-secret must not leak")
        except RuntimeError as error:
            raise HttpTransportUnavailable(HttpTransportFailureKind.TIMEOUT) from error


def make_provider(
    transport: FakeJsonTransport | UnavailableTransport,
    *,
    api_key: str | None = "test-key",
) -> MassiveAssetMetadataProvider:
    """创建测试用 Massive Adapter。"""

    return MassiveAssetMetadataProvider(
        api_key=api_key,
        base_url="https://api.example.test",
        timeout_seconds=3,
        transport=transport,
    )


def ticker_payload(
    ticker: str = "GOOG",
    *,
    name: str = "Alphabet Inc.",
    locale: str = "us",
    market: str = "stocks",
    active: bool = True,
) -> dict[str, object]:
    """创建 Massive ticker fixture。"""

    return {
        "ticker": ticker,
        "name": name,
        "primary_exchange": "XNAS",
        "locale": locale,
        "market": market,
        "active": active,
        "type": "CS",
    }


def test_search_maps_minimal_identity_and_filters_market_scope() -> None:
    """Adapter 只输出四个中立字段，并在边界过滤非美国/非 active 记录。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "status": "OK",
                    "results": [
                        ticker_payload("MSFT", name="Microsoft Corporation"),
                        ticker_payload("SPY", name="SPDR S&P 500 ETF Trust"),
                        ticker_payload("VOD", locale="gb"),
                        ticker_payload("DEAD", active=False),
                        ticker_payload("BTCUSD", market="crypto"),
                    ],
                },
            )
        ]
    )

    result = make_provider(transport).search(AssetSearchQuery("micro", limit=5))

    assert result.status is AssetMetadataStatus.OK
    assert [candidate.canonical_symbol for candidate in result.candidates] == ["MSFT", "SPY"]
    assert result.candidates[0].display_name == "Microsoft Corporation"
    assert result.candidates[0].exchange == "XNAS"
    assert result.candidates[0].status is AssetStatus.ACTIVE
    assert "market=stocks" in transport.requests[0].url
    assert "locale=us" in transport.requests[0].url
    assert "active=true" in transport.requests[0].url
    assert "limit=5" in transport.requests[0].url


def test_search_empty_results_is_no_match() -> None:
    """合法搜索无结果必须区别于 Provider Failure。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK", "results": []})])
    ).search(AssetSearchQuery("unknown"))

    assert result.status is AssetMetadataStatus.NO_MATCH
    assert result.candidates == ()


def test_exact_validation_maps_ticker_detail_and_requires_requested_symbol() -> None:
    """Exact Endpoint 返回的 canonical symbol 必须与请求一致。"""

    transport = FakeJsonTransport(
        [JsonHttpResponse(200, {"status": "OK", "results": ticker_payload("GOOG")})]
    )

    result = make_provider(transport).get_exact(AssetValidationQuery("goog"))

    assert result.status is AssetMetadataStatus.OK
    assert result.asset is not None
    assert result.asset.canonical_symbol == "GOOG"
    assert "/v3/reference/tickers/GOOG" in transport.requests[0].url

    mismatch = make_provider(
        FakeJsonTransport(
            [JsonHttpResponse(200, {"status": "OK", "results": ticker_payload("GOOGL")})]
        )
    ).get_exact(AssetValidationQuery("GOOG"))
    assert mismatch.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


def test_exact_distinguishes_missing_results_from_explicit_no_match() -> None:
    """缺失 results 是 malformed response，显式 null 才表示没有匹配。"""

    malformed = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK"})])
    ).get_exact(AssetValidationQuery("GOOG"))
    no_match = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK", "results": None})])
    ).get_exact(AssetValidationQuery("GOOG"))

    assert malformed.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE
    assert no_match.status is AssetMetadataStatus.NO_MATCH


@pytest.mark.parametrize("missing_field", ["ticker", "name", "primary_exchange"])
def test_exact_rejects_missing_required_asset_field(missing_field: str) -> None:
    """Provider 缺失 Selector 必需字段时应返回 INVALID_PROVIDER_RESPONSE。"""

    payload = ticker_payload("GOOG")
    payload.pop(missing_field)

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK", "results": payload})])
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


@pytest.mark.parametrize("missing_field", ["locale", "market", "active"])
def test_exact_rejects_missing_asset_scope_field(missing_field: str) -> None:
    """Provider 缺失市场范围字段时不能伪装成合法 NO_MATCH。"""

    payload = ticker_payload("GOOG")
    payload.pop(missing_field)

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK", "results": payload})])
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, AssetMetadataStatus.INVALID_REQUEST),
        (401, AssetMetadataStatus.AUTHENTICATION_FAILED),
        (403, AssetMetadataStatus.AUTHENTICATION_FAILED),
        (404, AssetMetadataStatus.NO_MATCH),
        (429, AssetMetadataStatus.RATE_LIMITED),
        (500, AssetMetadataStatus.PROVIDER_UNAVAILABLE),
        (418, AssetMetadataStatus.INVALID_PROVIDER_RESPONSE),
    ],
)
def test_exact_maps_http_failures_without_provider_payload(
    status_code: int,
    expected: AssetMetadataStatus,
) -> None:
    """HTTP Failure 应映射为稳定状态且不能泄露 Provider Payload。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(status_code, {"message": "test-secret"})])
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is expected
    assert result.message is not None
    assert "test-secret" not in result.message


def test_missing_credentials_fail_before_network_call() -> None:
    """缺少 API Key 时不应发出匿名请求。"""

    transport = FakeJsonTransport([])

    result = make_provider(transport, api_key=None).search(AssetSearchQuery("GOOG"))

    assert result.status is AssetMetadataStatus.AUTHENTICATION_FAILED
    assert transport.requests == []


def test_malformed_response_and_transport_failure_are_explicit() -> None:
    """Malformed JSON 与网络超时都不能伪装成空结果。"""

    malformed = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"status": "OK", "results": {}})])
    ).search(AssetSearchQuery("GOOG"))
    unavailable = make_provider(UnavailableTransport()).search(AssetSearchQuery("GOOG"))

    assert malformed.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE
    assert unavailable.status is AssetMetadataStatus.PROVIDER_UNAVAILABLE
    assert unavailable.message == "Massive 请求超时"
