"""Finnhub Asset Metadata Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self

import httpx2
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
    Httpx2JsonHttpTransport,
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


@dataclass(slots=True)
class FakeDirectoryTransport:
    """返回固定的美国证券目录。"""

    response: JsonHttpResponse = field(default_factory=lambda: JsonHttpResponse(200, []))

    def get_us_symbols(
        self,
        base_url: str,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        del base_url, api_key, timeout_seconds
        return self.response


@dataclass(slots=True)
class FakeHttpxResponse:
    """提供 httpx2 Transport 单元测试所需的最小 Response。"""

    status_code: int
    payload: object
    headers: Mapping[str, str] = field(default_factory=dict)

    def json(self) -> object:
        return self.payload


class FakeHttpxClient:
    """模拟 httpx2 Client，避免 Transport 单元测试访问网络。"""

    def __init__(
        self,
        response: FakeHttpxResponse | BaseException | list[FakeHttpxResponse],
    ) -> None:
        self._response = response
        self.requests: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str] | None = None,
    ) -> FakeHttpxResponse:
        self.requests.append((url, dict(headers), dict(params or {})))
        if isinstance(self._response, list):
            return self._response.pop(0)
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


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
        directory_transport=FakeDirectoryTransport(),
    )


def test_provider_uses_httpx2_transport_by_default() -> None:
    """Finnhub 默认必须使用可用的 httpx2 Transport，而不是 urllib。"""

    provider = FinnhubAssetMetadataProvider(api_key="test-key")

    assert isinstance(provider._transport, Httpx2JsonHttpTransport)


def test_httpx2_transport_maps_response_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx2 Transport 应保留 HTTP response，并把 timeout 映射为 Transport Failure。"""

    response = FakeHttpxResponse(200, {"result": []})
    client = FakeHttpxClient(response)
    client_options: list[dict[str, object]] = []

    def make_client(**kwargs: object) -> FakeHttpxClient:
        client_options.append(kwargs)
        return client

    monkeypatch.setattr(httpx2, "Client", make_client)

    transport = Httpx2JsonHttpTransport()
    result = transport.get_json(
        "https://api.example.test/search",
        headers={"Accept": "application/json"},
        timeout_seconds=3,
    )

    assert result == JsonHttpResponse(200, {"result": []})
    assert client_options == [{"timeout": 3, "trust_env": False}]

    timeout_client = FakeHttpxClient(httpx2.ReadTimeout("timeout"))
    monkeypatch.setattr(httpx2, "Client", lambda **kwargs: timeout_client)

    with pytest.raises(HttpTransportUnavailable) as error:
        transport.get_json(
            "https://api.example.test/search",
            headers={},
            timeout_seconds=3,
        )
    assert error.value.kind is HttpTransportFailureKind.TIMEOUT


def test_symbol_directory_follows_provider_redirect_without_credential_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """目录下载通过 Header 鉴权，重定向请求不携带 Credential。"""

    client = FakeHttpxClient(
        [
            FakeHttpxResponse(
                302,
                None,
                {"location": "https://static2.finnhub.io/file/exchange/US.json"},
            ),
            FakeHttpxResponse(200, [search_candidate("AAOI")]),
        ]
    )
    client_options: list[dict[str, object]] = []

    def make_client(**kwargs: object) -> FakeHttpxClient:
        client_options.append(kwargs)
        return client

    monkeypatch.setattr(httpx2, "Client", make_client)

    result = Httpx2JsonHttpTransport().get_us_symbols(
        "https://api.example.test/api/v1",
        api_key="test-key",
        timeout_seconds=3,
    )

    assert result == JsonHttpResponse(200, [search_candidate("AAOI")])
    assert client_options == [{"timeout": 3, "trust_env": False}]
    assert client.requests == [
        (
            "https://api.example.test/api/v1/stock/symbol",
            {"Accept": "application/json", "X-Finnhub-Token": "test-key"},
            {"exchange": "US"},
        ),
        (
            "https://static2.finnhub.io/file/exchange/US.json",
            {"Accept": "application/json"},
            {},
        ),
    ]


def test_symbol_directory_rejects_redirect_outside_finnhub_data_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """目录请求不得把 Finnhub 响应引导到未经允许的 Host。"""

    client = FakeHttpxClient(
        FakeHttpxResponse(302, None, {"location": "https://example.test/assets.json"})
    )
    monkeypatch.setattr(httpx2, "Client", lambda **kwargs: client)

    result = Httpx2JsonHttpTransport().get_us_symbols(
        "https://api.example.test/api/v1",
        api_key="test-key",
        timeout_seconds=3,
    )

    assert result == JsonHttpResponse(302, None)
    assert len(client.requests) == 1


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


def test_search_returns_exact_symbol_first_and_fills_requested_candidates() -> None:
    """精确 symbol 应排在首位，同时继续补足用户请求的联想候选。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "result": [
                        search_candidate("AAON", description="AAON Inc."),
                    ]
                },
            ),
            JsonHttpResponse(200, profile_payload("AAON", name="AAON Inc.")),
        ]
    )
    directory = FakeDirectoryTransport(
        JsonHttpResponse(
            200,
            [
                search_candidate("AAOX", description="TRADR 2X LONG AAOI", asset_type="ETP"),
                search_candidate("AAOG", description="LEVERAGE SHARES 2X AAOI", asset_type="ETP"),
                search_candidate("AAOI", description="Applied Optoelectronics"),
                search_candidate("AAON", description="AAON Inc."),
                search_candidate("AAOZ", description="TRADR 2X SHORT AAOI", asset_type="ETP"),
            ],
        )
    )

    result = FinnhubAssetMetadataProvider(
        api_key="test-key",
        base_url="https://api.example.test/api/v1",
        timeout_seconds=3,
        transport=transport,
        directory_transport=directory,
    ).search(AssetSearchQuery("AAO", limit=3))

    assert result.status is AssetMetadataStatus.OK
    assert [candidate.canonical_symbol for candidate in result.candidates] == [
        "AAON",
        "AAOI",
        "AAOX",
    ]
    assert len(transport.requests) == 2


def test_search_null_result_is_invalid_provider_response() -> None:
    """Finnhub 契约中的 result 应为数组，null 不能伪装成正常空结果。"""

    result = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"count": 0, "result": None})])
    ).search(AssetSearchQuery("unknown"))

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


def test_search_skips_candidate_when_profile_resolves_to_different_ticker() -> None:
    """候选别名不一致不能让其他已验证候选的整次搜索失败。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "result": [
                        search_candidate("GOOG"),
                        search_candidate("GOOG.ALIAS"),
                    ]
                },
            ),
            JsonHttpResponse(200, profile_payload("GOOG")),
            JsonHttpResponse(200, profile_payload("GOOG")),
        ]
    )

    result = make_provider(transport).search(AssetSearchQuery("GOOG", limit=5))

    assert result.status is AssetMetadataStatus.OK
    assert [candidate.canonical_symbol for candidate in result.candidates] == ["GOOG"]


def test_exact_validation_uses_exact_us_search_candidate() -> None:
    """exact validation 以 US-scoped Search 的精确 displaySymbol 建立 canonical identity。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(200, {"result": [search_candidate("GOOG")]}),
        ]
    )

    result = make_provider(transport).get_exact(AssetValidationQuery("goog"))

    assert result.status is AssetMetadataStatus.OK
    assert result.asset is not None
    assert result.asset.canonical_symbol == "GOOG"
    assert result.asset.display_name == "Alphabet Inc."
    assert result.asset.exchange == "US"
    assert len(transport.requests) == 1
    assert "/search?q=GOOG&exchange=US" in transport.requests[0].url
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


def test_exact_empty_search_is_no_match() -> None:
    """Provider 正常返回空 search 才能明确判为 NO_MATCH。"""

    no_search_match = make_provider(
        FakeJsonTransport([JsonHttpResponse(200, {"result": []})])
    ).get_exact(AssetValidationQuery("GOOG"))
    assert no_search_match.status is AssetMetadataStatus.NO_MATCH


def test_exact_null_search_result_is_invalid_provider_response() -> None:
    """Exact Lookup 的 null search result 也是 Provider 契约异常。"""

    result = make_provider(FakeJsonTransport([JsonHttpResponse(200, {"result": None})])).get_exact(
        AssetValidationQuery("GOOG")
    )

    assert result.status is AssetMetadataStatus.INVALID_PROVIDER_RESPONSE


def test_exact_requires_search_symbol_to_match_requested_symbol() -> None:
    """Search 没有精确 displaySymbol 时不能返回近似候选。"""

    result = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(200, {"result": [search_candidate("GOOGL")]}),
            ]
        )
    ).get_exact(AssetValidationQuery("GOOG"))

    assert result.status is AssetMetadataStatus.NO_MATCH


@pytest.mark.parametrize("missing_field", ["displaySymbol", "description"])
def test_exact_rejects_malformed_search_identity(missing_field: str) -> None:
    """精确 Search Candidate 缺少身份字段时返回 malformed，而非 INVALID。"""

    payload = search_candidate("GOOG")
    payload.pop(missing_field)
    result = make_provider(
        FakeJsonTransport(
            [
                JsonHttpResponse(200, {"result": [payload]}),
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
        (404, AssetMetadataStatus.PROVIDER_UNAVAILABLE),
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
