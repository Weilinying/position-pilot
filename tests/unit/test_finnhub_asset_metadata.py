"""Finnhub Asset Metadata Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from position_pilot.domain.asset_metadata import (
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetValidationQuery,
)
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailureKind,
    HttpTransportUnavailable,
    JsonHttpResponse,
)
from position_pilot.integrations.finnhub_asset_metadata import (
    FinnhubAssetMetadataProvider,
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


@dataclass(slots=True)
class UnavailableTransport:
    """模拟底层网络失败。"""

    kind: HttpTransportFailureKind

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        raise HttpTransportUnavailable(self.kind)


def make_provider(
    transport: FakeJsonTransport | UnavailableTransport,
    *,
    api_key: str | None = "test-key",
) -> FinnhubAssetMetadataProvider:
    """创建测试用 Finnhub Adapter。"""

    return FinnhubAssetMetadataProvider(
        api_key=api_key,
        base_url="https://api.example.test/api/v1",
        timeout_seconds=3,
        transport=transport,
    )


def search_candidate(
    symbol: str = "GOOG",
    *,
    description: str = "Alphabet Inc.",
    asset_type: str = "Common Stock",
) -> dict[str, object]:
    """创建 Finnhub search candidate fixture。"""

    return {
        "displaySymbol": symbol,
        "description": description,
        "symbol": symbol,
        "type": asset_type,
    }


def profile_payload(
    ticker: str = "GOOG",
    *,
    name: str = "Alphabet Inc.",
    exchange: str = "NASDAQ NMS - Global Market",
) -> dict[str, object]:
    """创建 Finnhub profile2 fixture。"""

    return {"ticker": ticker, "name": name, "exchange": exchange}


def test_search_maps_identity_filters_type_and_bounds_results() -> None:
    """搜索只输出三字段 identity、过滤非股票/ETF并遵守 limit。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "count": 5,
                    "result": [
                        search_candidate("MSFT", description="Microsoft Corporation"),
                        search_candidate(
                            "SPY", description="SPDR S&P 500 ETF Trust", asset_type="ETF"
                        ),
                        search_candidate("BITO", asset_type="ETP"),
                        search_candidate("VOD", asset_type="ADR"),
                        search_candidate("WARRANT", asset_type="Warrant"),
                    ],
                },
            ),
            JsonHttpResponse(
                200,
                profile_payload(
                    "MSFT",
                    name="Microsoft Corporation",
                    exchange="NASDAQ NMS - Global Market",
                ),
            ),
            JsonHttpResponse(
                200,
                profile_payload(
                    "SPY",
                    name="SPDR S&P 500 ETF Trust",
                    exchange="NYSE Arca",
                ),
            ),
            JsonHttpResponse(
                200,
                profile_payload(
                    "BITO",
                    name="ProShares Bitcoin Strategy ETF",
                    exchange="NYSE Arca",
                ),
            ),
        ]
    )

    result = make_provider(transport).search(AssetSearchQuery("micro", limit=3))

    assert result.status is AssetMetadataStatus.OK
    assert [candidate.canonical_symbol for candidate in result.candidates] == [
        "MSFT",
        "SPY",
        "BITO",
    ]
    assert result.candidates[0].display_name == "Microsoft Corporation"
    assert result.candidates[0].exchange == "NASDAQ NMS - GLOBAL MARKET"
    assert result.candidates[1].exchange == "NYSE ARCA"
    assert "q=micro" in transport.requests[0].url
    assert "exchange=US" in transport.requests[0].url
    assert len(transport.requests) == 4
    assert "test-key" not in transport.requests[0].url
    assert transport.requests[0].headers["X-Finnhub-Token"] == "test-key"


def test_search_empty_results_is_no_match() -> None:
    """合法搜索无结果必须区别于 Provider Failure。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"count": 0, "result": []})])
    ).search(AssetSearchQuery("unknown"))

    assert result.status is AssetMetadataStatus.NO_MATCH
    assert result.candidates == ()


def test_search_null_result_is_invalid_provider_response() -> None:
    """Finnhub 契约中的 result 应为数组，null 不能伪装成正常空结果。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"count": 0, "result": None})])
    ).search(AssetSearchQuery("unknown"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


def test_exact_validation_uses_exact_search_then_profile2() -> None:
    """exact validation 必须先命中 displaySymbol，再以 profile ticker 严格确认。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(200, {"result": [search_candidate("GOOG")]}),
            JsonHttpResponse(200, profile_payload()),
        ]
    )

    result = make_provider(transport).get_exact(AssetValidationQuery("goog"))

    assert result.status is AssetMetadataStatus.OK
    assert result.asset is not None
    assert result.asset.canonical_symbol == "GOOG"
    assert result.asset.display_name == "Alphabet Inc."
    assert result.asset.exchange == "NASDAQ NMS - GLOBAL MARKET"
    assert len(transport.requests) == 2
    assert "/search?q=GOOG&exchange=US" in transport.requests[0].url
    assert "/stock/profile2?symbol=GOOG" in transport.requests[1].url
    assert all("test-key" not in request.url for request in transport.requests)


def test_exact_validation_accepts_etp_search_candidate() -> None:
    """Finnhub 标记为 ETP 的 ETF 候选也应进入 exact validation。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {"result": [search_candidate("BITO", asset_type="ETP")]},
            ),
            JsonHttpResponse(200, profile_payload("BITO", name="ProShares Bitcoin ETF")),
        ]
    )

    result = make_provider(transport).get_exact(AssetValidationQuery("BITO"))

    assert result.status is AssetMetadataStatus.OK
    assert result.asset is not None
    assert result.asset.canonical_symbol == "BITO"


def test_exact_empty_search_or_profile_is_no_match() -> None:
    """空 search 与空 profile 都是明确的 NO_MATCH。"""

    no_search_match = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"result": []})])
    ).get_exact(AssetValidationQuery("GOOG"))
    no_profile_match = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(200, {"result": [search_candidate("GOOG")]}),
                JsonHttpResponse(200, {}),
            ]
        )
    ).get_exact(AssetValidationQuery("GOOG"))

    assert no_search_match.status is AssetMetadataStatus.NO_MATCH
    assert no_profile_match.status is AssetMetadataStatus.NO_MATCH


def test_exact_null_search_result_is_invalid_provider_response() -> None:
    """Exact Lookup 的 null search result 也是 Provider 契约异常。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"result": None})])
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


def test_exact_requires_provider_ticker_to_match_requested_symbol() -> None:
    """Profile ticker 不精确一致时不能返回未经确认的 identity。"""

    result = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(200, {"result": [search_candidate("GOOG")]}),
                JsonHttpResponse(200, profile_payload("GOOGL")),
            ]
        )
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


@pytest.mark.parametrize("missing_field", ["ticker", "name", "exchange"])
def test_exact_rejects_malformed_profile(missing_field: str) -> None:
    """非空 profile 缺少必需字段时返回 malformed，而非 NO_MATCH。"""

    payload = profile_payload()
    payload.pop(missing_field)
    result = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(200, {"result": [search_candidate("GOOG")]}),
                JsonHttpResponse(200, payload),
            ]
        )
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
        (503, AssetMetadataStatus.PROVIDER_UNAVAILABLE),
        (418, AssetMetadataStatus.INVALID_PROVIDER_RESPONSE),
    ],
)
def test_http_failures_map_without_provider_payload(
    status_code: int,
    expected: AssetMetadataStatus,
) -> None:
    """HTTP Failure 应映射为稳定状态且不能泄露 Provider Payload。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(status_code, {"message": "test-secret"})])
    ).search(AssetSearchQuery("GOOG"))

    assert result.status is expected
    assert result.message is not None
    assert "test-secret" not in result.message


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        (HttpTransportFailureKind.TIMEOUT, "Finnhub 请求超时"),
        (HttpTransportFailureKind.TLS_CERTIFICATE_ERROR, "Finnhub TLS 证书校验失败"),
    ],
)
def test_transport_failures_are_explicit(
    kind: HttpTransportFailureKind,
    message: str,
) -> None:
    """超时与 TLS 错误必须映射为安全、可操作的消息。"""

    result = make_provider(UnavailableTransport(kind)).search(AssetSearchQuery("GOOG"))

    assert result.status is AssetMetadataStatus.PROVIDER_UNAVAILABLE
    assert result.message is not None
    assert message in result.message


def test_missing_credentials_fail_before_network_call() -> None:
    """缺少 API Key 时不应发出匿名请求。"""

    transport = FakeJsonTransport([])

    result = make_provider(transport, api_key=None).search(AssetSearchQuery("GOOG"))

    assert result.status is AssetMetadataStatus.AUTHENTICATION_FAILED
    assert transport.requests == []


def test_malformed_response_is_explicit() -> None:
    """Malformed JSON 与错误 result 类型都不能伪装成空结果。"""

    malformed_json = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, [search_candidate("GOOG")])])
    ).search(AssetSearchQuery("GOOG"))
    malformed_result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"result": {}})])
    ).search(AssetSearchQuery("GOOG"))

    assert malformed_json.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE
    assert malformed_result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE
