"""Phase 3 Research 候选与受控 Page Fetch Prototype。"""

import ipaddress
import json
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlencode, urljoin, urlsplit

import httpx
from openai import OpenAI

from .contracts import (
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    SourceRecord,
    TraceEvent,
)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Application-owned Search Provider 的最小结果。"""

    source_id: str
    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """Search 正常、空结果与失败必须可区分。"""

    status: ResearchStatus
    hits: tuple[SearchHit, ...] = ()
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.status is ResearchStatus.COMPLETED:
            if not self.hits or self.failure is not None:
                raise ValueError("Search 成功必须有结果且无 Failure")
        elif self.status is ResearchStatus.NO_RESULTS:
            if self.hits or self.failure is not None:
                raise ValueError("Search 空结果不能包含 Hit 或 Failure")
        elif self.hits or not self.failure:
            raise ValueError("Search 失败必须只有安全 Failure")


class SearchProvider(Protocol):
    """Phase 3 只允许一个 Search Provider 实现。"""

    name: str

    def search(self, query: str, *, limit: int) -> SearchResponse: ...


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """受控 HTTP Transport 的最小响应。"""

    status_code: int
    headers: Mapping[str, str]
    body: bytes
    peer_ip: str | None = None


class HttpTransport(Protocol):
    """禁止自动 Redirect 的 HTTP Transport。"""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse: ...


class HttpxTransport:
    """禁用自动 Redirect，并对响应读取设置硬上限。"""

    def __init__(self, *, max_response_bytes: int = 512_000) -> None:
        self._max_response_bytes = max_response_bytes

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """流式读取有限字节，避免先下载无限正文再校验。"""

        with httpx.Client(follow_redirects=False, timeout=timeout_seconds) as client:
            with client.stream("GET", url, headers=dict(headers)) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        break
                network_stream = response.extensions.get("network_stream")
                server_address = (
                    network_stream.get_extra_info("server_addr")
                    if network_stream is not None
                    else None
                )
                peer_ip = (
                    server_address[0]
                    if isinstance(server_address, tuple)
                    and server_address
                    and isinstance(server_address[0], str)
                    else None
                )
                return HttpResponse(
                    response.status_code,
                    dict(response.headers),
                    bytes(body),
                    peer_ip,
                )


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Page Fetch 的有限状态。"""

    status: str
    final_url: str | None = None
    text: str | None = None
    failure: str | None = None


class ControlledPageFetcher:
    """只实现 SSRF、Redirect、Timeout 与 Size Boundary 的 Fetch Prototype。"""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        resolver: Callable[[str], Sequence[str]] | None = None,
        timeout_seconds: float = 5,
        max_bytes: int = 256_000,
        max_redirects: int = 3,
    ) -> None:
        self._transport = transport
        self._resolver = resolver or self._resolve
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects

    def fetch(self, url: str) -> FetchResult:
        """每次 Redirect 都重新验证目标；失败不返回不完整正文。"""

        current = url
        for redirect_count in range(self._max_redirects + 1):
            addresses, failure = self._validated_addresses(current)
            if failure is not None:
                return FetchResult("BLOCKED", failure=failure)
            try:
                response = self._transport.get(
                    current,
                    headers={"User-Agent": "PositionPilot-Phase3-Spike/1.0"},
                    timeout_seconds=self._timeout_seconds,
                )
            except TimeoutError:
                return FetchResult("TIMEOUT", failure="FETCH_TIMEOUT")
            except Exception as exc:  # noqa: BLE001 - Transport Failure 必须安全归一化。
                return FetchResult("PROVIDER_FAILURE", failure=type(exc).__name__)
            peer_failure = self._peer_failure(response.peer_ip, addresses)
            if peer_failure is not None:
                return FetchResult("BLOCKED", failure=peer_failure)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location") or response.headers.get("Location")
                if not location:
                    return FetchResult("PROVIDER_FAILURE", failure="REDIRECT_WITHOUT_LOCATION")
                if redirect_count >= self._max_redirects:
                    return FetchResult("BLOCKED", failure="TOO_MANY_REDIRECTS")
                current = urljoin(current, location)
                continue
            if response.status_code < 200 or response.status_code >= 300:
                return FetchResult(
                    "PROVIDER_FAILURE",
                    failure=f"HTTP_{response.status_code}",
                )
            if len(response.body) > self._max_bytes:
                return FetchResult("BLOCKED", failure="RESPONSE_TOO_LARGE")
            content_type = response.headers.get("content-type", "").lower()
            if content_type and not any(
                allowed in content_type for allowed in ("text/", "application/xhtml+xml")
            ):
                return FetchResult("BLOCKED", failure="UNSUPPORTED_CONTENT_TYPE")
            return FetchResult(
                "OK",
                final_url=current,
                text=response.body.decode("utf-8", errors="replace"),
            )
        raise AssertionError("Redirect Loop 必须在循环内结束")

    def _validated_addresses(self, url: str) -> tuple[tuple[str, ...], str | None]:
        """拒绝非公开 HTTP(S) 地址、Credential 与解析失败。"""

        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return (), "UNSUPPORTED_SCHEME"
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return (), "INVALID_URL_AUTHORITY"
        try:
            addresses = tuple(self._resolver(parsed.hostname))
        except OSError:
            return (), "DNS_RESOLUTION_FAILED"
        if not addresses:
            return (), "DNS_RESOLUTION_FAILED"
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                return (), "INVALID_DNS_ADDRESS"
            if not address.is_global:
                return (), "NON_PUBLIC_DESTINATION"
        return addresses, None

    def _peer_failure(self, peer_ip: str | None, resolved: tuple[str, ...]) -> str | None:
        """真实 Transport 必须校验连接 Peer，避免 DNS Rebinding 绕过预检查。"""

        if peer_ip is None:
            return (
                "PEER_ADDRESS_UNAVAILABLE" if isinstance(self._transport, HttpxTransport) else None
            )
        try:
            peer_address = ipaddress.ip_address(peer_ip)
        except ValueError:
            return "INVALID_PEER_ADDRESS"
        if not peer_address.is_global or peer_ip not in resolved:
            return "PEER_ADDRESS_MISMATCH"
        return None

    @staticmethod
    def _resolve(hostname: str) -> tuple[str, ...]:
        """解析全部地址，避免只验证第一个 DNS 结果。"""

        return tuple(
            sorted(
                {
                    item[4][0]
                    for item in socket.getaddrinfo(
                        hostname,
                        None,
                        type=socket.SOCK_STREAM,
                    )
                    if isinstance(item[4][0], str)
                }
            )
        )


class PageFetcher(Protocol):
    """Application-owned Research 可使用独立受控 Fetch 实现。"""

    def fetch(self, url: str) -> FetchResult: ...


class BraveSearchProvider:
    """Phase 3 唯一 Application-owned Search Provider 候选。"""

    name = "brave-search"

    def __init__(
        self,
        transport: HttpTransport,
        *,
        api_key: str,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
        timeout_seconds: float = 5,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Brave Search API Key 不能为空")
        self._transport = transport
        self._api_key = api_key
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    def search(self, query: str, *, limit: int) -> SearchResponse:
        """调用一个 Search Provider，并只映射来源所需字段。"""

        if not query.strip() or limit <= 0:
            raise ValueError("Search Query 与 Limit 必须有效")
        url = f"{self._endpoint}?{urlencode({'q': query, 'count': limit})}"
        try:
            response = self._transport.get(
                url,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._api_key,
                },
                timeout_seconds=self._timeout_seconds,
            )
        except TimeoutError:
            return SearchResponse(ResearchStatus.PROVIDER_FAILURE, failure="SEARCH_TIMEOUT")
        except Exception as exc:  # noqa: BLE001 - Provider Failure 必须安全归一化。
            return SearchResponse(
                ResearchStatus.PROVIDER_FAILURE,
                failure=type(exc).__name__,
            )
        if response.status_code < 200 or response.status_code >= 300:
            return SearchResponse(
                ResearchStatus.PROVIDER_FAILURE,
                failure=f"SEARCH_HTTP_{response.status_code}",
            )
        try:
            payload = json.loads(response.body)
            raw_hits = payload.get("web", {}).get("results", [])
            hits = tuple(
                SearchHit(
                    f"brave-{index}",
                    item["url"],
                    item.get("title"),
                    item.get("profile", {}).get("long_name"),
                    item.get("age"),
                )
                for index, item in enumerate(raw_hits[:limit], start=1)
                if isinstance(item, dict) and isinstance(item.get("url"), str)
            )
        except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return SearchResponse(
                ResearchStatus.PROVIDER_FAILURE,
                failure="INVALID_SEARCH_RESPONSE",
            )
        if not hits:
            return SearchResponse(ResearchStatus.NO_RESULTS)
        return SearchResponse(ResearchStatus.COMPLETED, hits)


class ApplicationOwnedResearchCandidate:
    """一个 Search Provider 加独立受控 Fetch 的 Research 路径。"""

    name = "application-owned"

    def __init__(
        self,
        search_provider: SearchProvider,
        fetcher: PageFetcher,
        *,
        result_limit: int = 3,
        fetch_limit: int = 1,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._search_provider = search_provider
        self._fetcher = fetcher
        self._result_limit = result_limit
        self._fetch_limit = fetch_limit
        self._clock = clock

    def research(self, request: ResearchRequest) -> ResearchResult:
        """搜索公开请求并受控读取最多一个页面。"""

        started_at = self._clock()
        response = self._search_provider.search(request.query, limit=self._result_limit)
        if response.status is ResearchStatus.NO_RESULTS:
            return ResearchResult(
                request,
                ResearchStatus.NO_RESULTS,
                search_count=1,
                latency_ms=self._latency_ms(started_at),
            )
        if response.status is not ResearchStatus.COMPLETED:
            return ResearchResult(
                request,
                ResearchStatus.PROVIDER_FAILURE,
                failure=response.failure or "SEARCH_PROVIDER_FAILURE",
                research_trace=(TraceEvent("research", 1, "PROVIDER_FAILURE", "search"),),
                search_count=1,
                latency_ms=self._latency_ms(started_at),
            )

        sources: list[SourceRecord] = []
        trace: list[TraceEvent] = []
        fetch_failures: list[str] = []
        for index, hit in enumerate(response.hits):
            fetch_result = (
                self._fetcher.fetch(hit.url)
                if index < self._fetch_limit
                else FetchResult("NOT_FETCHED", final_url=hit.url)
            )
            fetch_status = fetch_result.status
            if fetch_status not in {"OK", "NOT_FETCHED"}:
                fetch_failures.append(fetch_result.failure or fetch_status)
            source = SourceRecord(
                hit.source_id,
                self._search_provider.name,
                fetch_result.final_url or hit.url,
                hit.title,
                publisher=hit.publisher,
                published_at=hit.published_at,
                content_scope="FULL_TEXT" if fetch_status == "OK" else "SEARCH_SNIPPET",
                fetch_status=fetch_status,
            )
            sources.append(source)
            trace.append(
                TraceEvent(
                    "research",
                    len(trace) + 1,
                    "PARTIAL_SUCCESS" if fetch_failures else "OK",
                    "fetch" if index < self._fetch_limit else "search",
                    source.source_id,
                )
            )
        status = ResearchStatus.PARTIAL_SUCCESS if fetch_failures else ResearchStatus.COMPLETED
        return ResearchResult(
            request,
            status,
            tuple(sources),
            ";".join(fetch_failures) if fetch_failures else None,
            tuple(trace),
            search_count=1,
            fetch_count=min(len(response.hits), self._fetch_limit),
            latency_ms=self._latency_ms(started_at),
        )

    def _latency_ms(self, started_at: float) -> float:
        """记录 Search 与 Fetch 总耗时。"""

        return max(0.0, (self._clock() - started_at) * 1000)


@dataclass(frozen=True, slots=True)
class NativeResearchObservation:
    """Alibaba Responses Gateway 归一化后的最小观察。"""

    status: ResearchStatus
    sources: tuple[SourceRecord, ...] = ()
    failure: str | None = None
    search_count: int = 0
    fetch_count: int = 0


class NativeResearchGateway(Protocol):
    """固定模型的 Alibaba Native Research 调用边界。"""

    def run(self, *, model: str, query: str) -> NativeResearchObservation: ...


class AlibabaResponsesGateway:
    """通过 Alibaba OpenAI-compatible Responses API 调用原生研究工具。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip() or not base_url.strip():
            raise ValueError("Alibaba Responses Credential 与 Base URL 不能为空")
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)

    def run(self, *, model: str, query: str) -> NativeResearchObservation:
        """启用 Native web_search / web_extractor，并提取实际 URL Citation。"""

        try:
            # Alibaba 已支持 web_extractor，但当前 OpenAI SDK TypedDict 尚未包含该扩展。
            native_tools: Any = [{"type": "web_search"}, {"type": "web_extractor"}]
            response = self._client.responses.create(
                model=model,
                input=query,
                tools=native_tools,
            )
        except Exception as exc:  # noqa: BLE001 - Online Provider Failure 只记录安全类型。
            return NativeResearchObservation(
                ResearchStatus.PROVIDER_FAILURE,
                failure=type(exc).__name__,
            )
        payload = response.model_dump(mode="json")
        output = payload.get("output", [])
        if not isinstance(output, list):
            return NativeResearchObservation(
                ResearchStatus.PROVIDER_FAILURE,
                failure="INVALID_NATIVE_RESPONSE",
            )
        search_count = sum(
            1 for item in output if isinstance(item, dict) and item.get("type") == "web_search_call"
        )
        fetch_count = sum(
            1
            for item in output
            if isinstance(item, dict) and item.get("type") == "web_extractor_call"
        )
        citations: dict[str, SourceRecord] = {}
        for item in output:
            if not isinstance(item, dict):
                continue
            contents = item.get("content", [])
            if not isinstance(contents, list):
                continue
            for content in contents:
                if not isinstance(content, dict):
                    continue
                annotations = content.get("annotations", [])
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    if not isinstance(annotation, dict):
                        continue
                    url = annotation.get("url")
                    if annotation.get("type") != "url_citation" or not isinstance(url, str):
                        continue
                    source_id = f"native-{sha256(url.encode()).hexdigest()[:12]}"
                    citations[source_id] = SourceRecord(
                        source_id,
                        "ALIBABA_NATIVE",
                        url,
                        annotation.get("title")
                        if isinstance(annotation.get("title"), str)
                        else None,
                        provider_reference=annotation.get("id")
                        if isinstance(annotation.get("id"), str)
                        else None,
                        content_scope="PROVIDER_MANAGED",
                        fetch_status="OK" if fetch_count else "UNKNOWN",
                    )
        if not citations:
            status = ResearchStatus.NO_RESULTS if search_count else ResearchStatus.PROVIDER_FAILURE
            return NativeResearchObservation(
                status,
                failure=None
                if status is ResearchStatus.NO_RESULTS
                else "NO_OBSERVABLE_NATIVE_SOURCE",
                search_count=search_count,
                fetch_count=fetch_count,
            )
        return NativeResearchObservation(
            ResearchStatus.COMPLETED,
            tuple(citations.values()),
            search_count=search_count,
            fetch_count=fetch_count,
        )


class AlibabaNativeResearchCandidate:
    """不更换 Runtime 固定模型的 Native Research 候选。"""

    name = "alibaba-native"

    def __init__(
        self,
        gateway: NativeResearchGateway,
        *,
        model: str,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._gateway = gateway
        self._model = model
        self._clock = clock

    def research(self, request: ResearchRequest) -> ResearchResult:
        """只向 Provider 发送 Public-only Query，并保留来源观察。"""

        started_at = self._clock()
        observation = self._gateway.run(model=self._model, query=request.query)
        trace = tuple(
            TraceEvent(
                "research",
                index,
                "OK"
                if observation.status is ResearchStatus.COMPLETED
                else observation.status.value,
                "native-search",
                source.source_id,
            )
            for index, source in enumerate(observation.sources, start=1)
        )
        return ResearchResult(
            request,
            observation.status,
            observation.sources,
            observation.failure,
            trace,
            observation.search_count,
            observation.fetch_count,
            max(0.0, (self._clock() - started_at) * 1000),
        )
