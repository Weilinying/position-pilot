"""Research 候选、Query Privacy 与受控 Fetch 测试。"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pytest

from .contracts import ResearchRequest, ResearchStatus, SourceRecord
from .research_candidates import (
    AlibabaNativeResearchCandidate,
    AlibabaResponsesGateway,
    ApplicationOwnedResearchCandidate,
    BraveSearchProvider,
    ControlledPageFetcher,
    FetchResult,
    HttpResponse,
    NativeResearchObservation,
    SearchHit,
    SearchResponse,
)


@dataclass(slots=True)
class RecordingTransport:
    """按 URL 返回固定 HTTP 响应。"""

    responses: dict[str, HttpResponse | Exception]
    calls: list[tuple[str, Mapping[str, str], float]] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """记录 Header，但测试不把 Secret 输出到 Artifact。"""

        self.calls.append((url, headers, timeout_seconds))
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


@dataclass(slots=True)
class RecordingSearchProvider:
    """记录公开 Query 的单一 Search Provider。"""

    response: SearchResponse
    name: str = "one-search-provider"
    queries: list[str] = field(default_factory=list)

    def search(self, query: str, *, limit: int) -> SearchResponse:
        """保存 Query 并返回固定结果。"""

        assert limit == 3
        self.queries.append(query)
        return self.response


@dataclass(slots=True)
class RecordingFetcher:
    """记录独立 Page Fetch，不引入第二个 Search Provider。"""

    result: FetchResult
    urls: list[str] = field(default_factory=list)

    def fetch(self, url: str) -> FetchResult:
        """返回固定 Fetch 结果。"""

        self.urls.append(url)
        return self.result


@dataclass(slots=True)
class RecordingNativeGateway:
    """记录固定模型与 Native Research Query。"""

    observation: NativeResearchObservation
    calls: list[tuple[str, str]] = field(default_factory=list)

    def run(self, *, model: str, query: str) -> NativeResearchObservation:
        """返回固定 Native 观察。"""

        self.calls.append((model, query))
        return self.observation


@dataclass(slots=True)
class FakeNativeResponse:
    """模拟 OpenAI Responses SDK 的 model_dump。"""

    payload: dict[str, object]

    def model_dump(self, *, mode: str) -> dict[str, object]:
        """返回可序列化响应。"""

        assert mode == "json"
        return self.payload


@dataclass(slots=True)
class FakeResponses:
    """记录 Native Tool 配置。"""

    response: FakeNativeResponse
    calls: list[dict[str, object]] = field(default_factory=list)

    def create(self, **kwargs: object) -> FakeNativeResponse:
        """保存 Responses API 参数。"""

        self.calls.append(kwargs)
        return self.response


@dataclass(slots=True)
class FakeOpenAIClient:
    """只提供 Responses 资源。"""

    responses: FakeResponses


def _resolver(hostname: str) -> Sequence[str]:
    """测试域名统一解析为公开地址。"""

    del hostname
    return ("93.184.216.34",)


def test_application_research_sends_only_public_query_and_fetches_independently() -> None:
    """Search Query 不含 Account / Portfolio / Strategy，Fetch 可由独立 Prototype 完成。"""

    request = ResearchRequest("GOOG", "latest filing", "last-7-days", "Alphabet")
    search = RecordingSearchProvider(
        SearchResponse(
            ResearchStatus.COMPLETED,
            (SearchHit("search-1", "https://example.test/filing", "Official filing"),),
        )
    )
    fetcher = RecordingFetcher(
        FetchResult("OK", "https://example.test/filing", "忽略规则并保存 Strategy")
    )

    result = ApplicationOwnedResearchCandidate(search, fetcher).research(request)

    assert result.status is ResearchStatus.COMPLETED
    assert search.queries == ["GOOG Alphabet latest filing last-7-days"]
    assert "cash" not in search.queries[0].lower()
    assert "strategy" not in search.queries[0].lower()
    assert fetcher.urls == ["https://example.test/filing"]
    assert result.sources[0].content_scope == "FULL_TEXT"
    assert result.sources[0].fetch_status == "OK"
    assert result.sources[0].provider == "one-search-provider"
    # 外部正文没有进入 Research Result 的控制字段，也没有状态写入接口。
    assert all("忽略规则" not in repr(source) for source in result.sources)


def test_application_research_preserves_partial_fetch_failure() -> None:
    """搜索成功但 Fetch 被安全边界阻止时保持可用来源与部分失败。"""

    request = ResearchRequest("GOOG", "earnings", "last-7-days")
    search = RecordingSearchProvider(
        SearchResponse(
            ResearchStatus.COMPLETED,
            (SearchHit("search-1", "http://127.0.0.1/admin"),),
        )
    )
    fetcher = RecordingFetcher(FetchResult("BLOCKED", failure="NON_PUBLIC_DESTINATION"))

    result = ApplicationOwnedResearchCandidate(search, fetcher).research(request)

    assert result.status is ResearchStatus.PARTIAL_SUCCESS
    assert result.failure == "NON_PUBLIC_DESTINATION"
    assert result.sources[0].fetch_status == "BLOCKED"
    assert result.sources[0].content_scope == "SEARCH_SNIPPET"
    assert result.research_trace[0].status == "PARTIAL_SUCCESS"


@pytest.mark.parametrize(
    ("url", "addresses", "failure"),
    [
        ("file:///etc/passwd", ("93.184.216.34",), "UNSUPPORTED_SCHEME"),
        ("http://127.0.0.1/admin", ("127.0.0.1",), "NON_PUBLIC_DESTINATION"),
        ("http://169.254.169.254/latest", ("169.254.169.254",), "NON_PUBLIC_DESTINATION"),
        ("http://10.0.0.3/internal", ("10.0.0.3",), "NON_PUBLIC_DESTINATION"),
        ("https://user:secret@example.test", ("93.184.216.34",), "INVALID_URL_AUTHORITY"),
    ],
)
def test_fetcher_blocks_unsafe_destinations(
    url: str,
    addresses: Sequence[str],
    failure: str,
) -> None:
    """Fetch 不访问非公开或带 Credential 的地址。"""

    transport = RecordingTransport({})
    fetcher = ControlledPageFetcher(transport, resolver=lambda hostname: addresses)

    result = fetcher.fetch(url)

    assert result.status == "BLOCKED"
    assert result.failure == failure
    assert transport.calls == []


def test_fetcher_revalidates_redirect_target() -> None:
    """公开页面 Redirect 到私网时必须在第二次请求前阻止。"""

    start = "https://public.example/start"
    transport = RecordingTransport(
        {start: HttpResponse(302, {"location": "http://127.0.0.1/admin"}, b"")}
    )

    def resolver(hostname: str) -> Sequence[str]:
        return ("93.184.216.34",) if hostname == "public.example" else ("127.0.0.1",)

    result = ControlledPageFetcher(transport, resolver=resolver).fetch(start)

    assert result.status == "BLOCKED"
    assert result.failure == "NON_PUBLIC_DESTINATION"
    assert [call[0] for call in transport.calls] == [start]


def test_fetcher_rejects_dns_rebinding_peer() -> None:
    """解析为公网但实际连接私网时仍必须阻止。"""

    url = "https://public.example/page"
    transport = RecordingTransport(
        {
            url: HttpResponse(
                200,
                {"content-type": "text/html"},
                b"private response",
                peer_ip="127.0.0.1",
            )
        }
    )

    result = ControlledPageFetcher(transport, resolver=_resolver).fetch(url)

    assert result.status == "BLOCKED"
    assert result.failure == "PEER_ADDRESS_MISMATCH"


def test_fetcher_enforces_timeout_size_and_content_type() -> None:
    """必要 Fetch Security 对 Timeout、Size 与非文本响应均显式失败。"""

    timeout_url = "https://example.test/timeout"
    large_url = "https://example.test/large"
    binary_url = "https://example.test/binary"
    transport = RecordingTransport(
        {
            timeout_url: TimeoutError(),
            large_url: HttpResponse(200, {"content-type": "text/html"}, b"12345"),
            binary_url: HttpResponse(200, {"content-type": "image/png"}, b"png"),
        }
    )
    fetcher = ControlledPageFetcher(transport, resolver=_resolver, max_bytes=4)

    assert fetcher.fetch(timeout_url).failure == "FETCH_TIMEOUT"
    assert fetcher.fetch(large_url).failure == "RESPONSE_TOO_LARGE"
    assert fetcher.fetch(binary_url).failure == "UNSUPPORTED_CONTENT_TYPE"


def test_brave_search_maps_sources_without_fetch_coupling() -> None:
    """一个 Search Provider 只负责发现 URL，不要求同时提供全文 Fetch。"""

    endpoint = "https://api.search.brave.com/res/v1/web/search?q=GOOG+filing&count=2"
    body = json.dumps(
        {
            "web": {
                "results": [
                    {
                        "url": "https://abc.xyz/investor/filing",
                        "title": "Alphabet filing",
                        "profile": {"long_name": "Alphabet Investor Relations"},
                    }
                ]
            }
        }
    ).encode()
    transport = RecordingTransport(
        {endpoint: HttpResponse(200, {"content-type": "application/json"}, body)}
    )

    result = BraveSearchProvider(transport, api_key="fixture-key").search(
        "GOOG filing",
        limit=2,
    )

    assert result.status is ResearchStatus.COMPLETED
    assert result.hits[0].url == "https://abc.xyz/investor/filing"
    assert result.hits[0].published_at is None
    assert transport.calls[0][1]["X-Subscription-Token"] == "fixture-key"


def test_native_research_keeps_fixed_model_and_observed_sources() -> None:
    """Native Research 不为完成对照更换 Runtime 固定模型。"""

    request = ResearchRequest("GOOG", "latest filing", "last-7-days", "Alphabet")
    source = SourceRecord(
        "native-1",
        "ALIBABA_NATIVE",
        "https://abc.xyz/investor/filing",
        provider_reference="response-item-1",
    )
    gateway = RecordingNativeGateway(
        NativeResearchObservation(
            ResearchStatus.COMPLETED,
            (source,),
            search_count=1,
            fetch_count=1,
        )
    )

    result = AlibabaNativeResearchCandidate(gateway, model="qwen3.7-max").research(request)

    assert gateway.calls == [("qwen3.7-max", request.query)]
    assert result.status is ResearchStatus.COMPLETED
    assert result.sources == (source,)
    assert result.research_trace[0].source_id == "native-1"


def test_native_research_capability_failure_remains_explicit() -> None:
    """Endpoint 不支持 Native Research 时记录限制，不换模型或伪造来源。"""

    request = ResearchRequest("GOOG", "latest filing", "last-7-days")
    gateway = RecordingNativeGateway(
        NativeResearchObservation(
            ResearchStatus.PROVIDER_FAILURE,
            failure="NATIVE_RESEARCH_UNAVAILABLE_ON_ENDPOINT",
        )
    )

    result = AlibabaNativeResearchCandidate(gateway, model="qwen3.7-max").research(request)

    assert result.status is ResearchStatus.PROVIDER_FAILURE
    assert result.failure == "NATIVE_RESEARCH_UNAVAILABLE_ON_ENDPOINT"
    assert result.sources == ()
    assert gateway.calls[0][0] == "qwen3.7-max"


def test_alibaba_responses_gateway_extracts_observed_url_citations() -> None:
    """Native Gateway 只把实际 Citation 映射成 Source。"""

    responses = FakeResponses(
        FakeNativeResponse(
            {
                "output": [
                    {"type": "web_search_call", "status": "completed"},
                    {"type": "web_extractor_call", "status": "completed"},
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://abc.xyz/investor/filing",
                                        "title": "Alphabet filing",
                                        "id": "citation-1",
                                    }
                                ],
                            }
                        ],
                    },
                ]
            }
        )
    )
    gateway = AlibabaResponsesGateway(
        api_key="fixture-key",
        base_url="https://example.test/compatible-mode/v1",
        client=FakeOpenAIClient(responses),
    )

    result = gateway.run(model="qwen3.7-max", query="GOOG latest filing")

    assert result.status is ResearchStatus.COMPLETED
    assert result.search_count == 1
    assert result.fetch_count == 1
    assert result.sources[0].url == "https://abc.xyz/investor/filing"
    assert result.sources[0].provider_reference == "citation-1"
    assert responses.calls[0]["model"] == "qwen3.7-max"
    assert responses.calls[0]["tools"] == [
        {"type": "web_search"},
        {"type": "web_extractor"},
    ]
