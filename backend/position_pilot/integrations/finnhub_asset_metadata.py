"""Finnhub Asset Metadata API 的 Provider Adapter。"""

import logging
from collections.abc import Mapping
from time import monotonic
from urllib.parse import urlencode

from position_pilot.application.asset_metadata_service import AssetMetadataProvider
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetValidationQuery,
    AssetValidationResult,
    InvalidAssetMetadata,
    normalize_asset_symbol,
)
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailure,
    HttpTransportUnavailable,
    JsonHttpResponse,
    JsonHttpTransport,
    UrllibJsonHttpTransport,
)

FINNHUB_SOURCE = "FINNHUB"
FINNHUB_DEFAULT_BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_EXCHANGE_SCOPE = "US"
_SUPPORTED_SEARCH_TYPES = frozenset({"common stock", "etf", "etp"})
logger = logging.getLogger(__name__)


class FinnhubAssetMetadataProvider(AssetMetadataProvider):
    """将 Finnhub 搜索与 Profile 数据映射为最小 Provider-neutral Asset Contract。"""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = FINNHUB_DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        transport: JsonHttpTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibJsonHttpTransport()

    def search(self, query: AssetSearchQuery) -> AssetSearchResult:
        """搜索美国普通股与 ETF，并将结果数量限制在 bounded query 内。"""

        if not isinstance(query, AssetSearchQuery):
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_REQUEST,
                "Finnhub search query 类型无效",
            )
        if not self._has_credentials():
            return AssetSearchResult.failure(
                AssetMetadataStatus.AUTHENTICATION_FAILED,
                "Finnhub API credential 未配置",
            )

        response = self._get(
            "/search",
            {"q": query.query, "exchange": FINNHUB_EXCHANGE_SCOPE},
        )
        if isinstance(response, HttpTransportFailure):
            return AssetSearchResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(response),
            )
        failure = self._response_failure(response)
        if failure is not None:
            return AssetSearchResult.failure(*failure)

        payload = self._mapping_payload(response)
        if payload is None:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 不是有效的 JSON object",
            )
        if "result" not in payload:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 缺少 result 字段",
            )
        raw_results = payload["result"]
        if raw_results is None:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 的 result 不能为 null",
            )
        if not isinstance(raw_results, list):
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 的 result 格式无效",
            )
        if not raw_results:
            return AssetSearchResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Finnhub 没有找到匹配 Asset",
            )

        candidates: list[AssetIdentity] = []
        profile_attempts = 0
        try:
            for raw_result in raw_results:
                if not isinstance(raw_result, Mapping):
                    return AssetSearchResult.failure(
                        AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                        "Finnhub search result 不是 JSON object",
                    )
                if not self._is_supported_search_type(raw_result):
                    continue
                if profile_attempts >= query.limit:
                    break
                profile_attempts += 1
                symbol = normalize_asset_symbol(
                    self._required_text(raw_result, "displaySymbol")
                )
                profile_result = self._get_profile_identity(
                    symbol,
                    ticker_mismatch_status=AssetMetadataStatus.NO_MATCH,
                )
                if profile_result.status is AssetMetadataStatus.NO_MATCH:
                    continue
                if profile_result.status is not AssetMetadataStatus.OK:
                    return AssetSearchResult.failure(
                        profile_result.status,
                        profile_result.message or "Finnhub profile 查询失败",
                    )
                if profile_result.asset is None:
                    return AssetSearchResult.failure(
                        AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                        "Finnhub profile validation 未返回 Asset",
                    )
                candidates.append(profile_result.asset)
        except InvalidAssetMetadata as error:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                f"Finnhub Asset 字段格式无效: {error}",
            )

        if not candidates:
            return AssetSearchResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "没有找到可用于 PositionPilot 的美国股票或 ETF",
            )
        return AssetSearchResult.success(tuple(candidates))

    def get_exact(self, query: AssetValidationQuery) -> AssetValidationResult:
        """先确认 US search candidate，再用免费 Profile 2 获取 exact identity。"""

        if not isinstance(query, AssetValidationQuery):
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_REQUEST,
                "Finnhub validation query 类型无效",
            )
        if not self._has_credentials():
            return AssetValidationResult.failure(
                AssetMetadataStatus.AUTHENTICATION_FAILED,
                "Finnhub API credential 未配置",
            )

        search_response = self._get(
            "/search",
            {"q": query.symbol, "exchange": FINNHUB_EXCHANGE_SCOPE},
        )
        if isinstance(search_response, HttpTransportFailure):
            return AssetValidationResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(search_response),
            )
        failure = self._response_failure(search_response)
        if failure is not None:
            return AssetValidationResult.failure(*failure)
        search_payload = self._mapping_payload(search_response)
        if search_payload is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 不是有效的 JSON object",
            )
        if "result" not in search_payload:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 缺少 result 字段",
            )
        raw_results = search_payload["result"]
        if raw_results is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 的 result 不能为 null",
            )
        if raw_results == []:
            return AssetValidationResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Finnhub 没有找到对应 Asset",
            )
        if not isinstance(raw_results, list):
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub search response 的 result 格式无效",
            )

        exact_candidate: Mapping[str, object] | None = None
        try:
            for raw_result in raw_results:
                if not isinstance(raw_result, Mapping):
                    return AssetValidationResult.failure(
                        AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                        "Finnhub search result 不是 JSON object",
                    )
                if not self._is_supported_search_type(raw_result):
                    continue
                display_symbol = raw_result.get("displaySymbol")
                if not isinstance(display_symbol, str):
                    return AssetValidationResult.failure(
                        AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                        "Finnhub search result 的 displaySymbol 格式无效",
                    )
                if display_symbol == query.symbol:
                    exact_candidate = raw_result
                    break
        except InvalidAssetMetadata as error:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                f"Finnhub Asset 字段格式无效: {error}",
            )
        if exact_candidate is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Finnhub 没有找到对应 Asset",
            )

        return self._get_profile_identity(
            query.symbol,
            ticker_mismatch_status=AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
        )

    def _get_profile_identity(
        self,
        symbol: str,
        *,
        ticker_mismatch_status: AssetMetadataStatus,
    ) -> AssetValidationResult:
        """用免费 Profile 2 补齐并精确验证最小 Asset Identity。"""

        profile_response = self._get("/stock/profile2", {"symbol": symbol})
        if isinstance(profile_response, HttpTransportFailure):
            return AssetValidationResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(profile_response),
            )
        failure = self._response_failure(profile_response)
        if failure is not None:
            return AssetValidationResult.failure(*failure)
        profile_payload = self._mapping_payload(profile_response)
        if profile_payload is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Finnhub profile response 不是有效的 JSON object",
            )
        if not profile_payload:
            return AssetValidationResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Finnhub 没有找到对应 Asset Profile",
            )
        try:
            ticker = self._required_text(profile_payload, "ticker")
            if ticker != symbol:
                return AssetValidationResult.failure(
                    ticker_mismatch_status,
                    "Finnhub profile 的 ticker 与请求不一致",
                )
            asset = AssetIdentity(
                canonical_symbol=ticker,
                display_name=self._required_text(profile_payload, "name"),
                exchange=self._required_text(profile_payload, "exchange"),
            )
        except InvalidAssetMetadata as error:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                f"Finnhub profile 字段格式无效: {error}",
            )
        return AssetValidationResult.success(asset)

    def _get(
        self,
        path: str,
        parameters: Mapping[str, str],
    ) -> JsonHttpResponse | HttpTransportFailure:
        """执行不含 URL credential 的 Finnhub GET，并记录 provider 与耗时。"""

        url = f"{self._base_url}{path}?{urlencode(parameters)}"
        started_at = monotonic()
        try:
            response = self._transport.get_json(
                url,
                headers={
                    "Accept": "application/json",
                    "X-Finnhub-Token": self._api_key or "",
                },
                timeout_seconds=self._timeout_seconds,
            )
            logger.info(
                "asset_metadata_provider_call",
                extra={
                    "provider": FINNHUB_SOURCE,
                    "http_status": response.status_code,
                    "latency_ms": round((monotonic() - started_at) * 1000, 2),
                },
            )
            return response
        except HttpTransportUnavailable as error:
            logger.warning(
                "asset_metadata_provider_failure",
                extra={
                    "provider": FINNHUB_SOURCE,
                    "failure_kind": error.kind.value,
                    "latency_ms": round((monotonic() - started_at) * 1000, 2),
                },
            )
            return HttpTransportFailure(error.kind)

    @staticmethod
    def _mapping_payload(response: JsonHttpResponse) -> Mapping[str, object] | None:
        """只接受 JSON object，避免把 Provider 错误字符串当作空结果。"""

        if isinstance(response.payload, Mapping):
            return response.payload
        return None

    @staticmethod
    def _response_failure(
        response: JsonHttpResponse,
    ) -> tuple[AssetMetadataStatus, str] | None:
        """把 HTTP 状态映射为稳定且不泄露 Provider Payload 的结果。"""

        status_code = response.status_code
        if 200 <= status_code < 300:
            return None
        if status_code in {400, 422}:
            return AssetMetadataStatus.INVALID_REQUEST, "Finnhub 拒绝了请求参数"
        if status_code in {401, 403}:
            return AssetMetadataStatus.AUTHENTICATION_FAILED, "Finnhub credential 无效或无权访问"
        if status_code == 404:
            return AssetMetadataStatus.NO_MATCH, "Finnhub 没有找到对应 Asset"
        if status_code == 429:
            return AssetMetadataStatus.RATE_LIMITED, "Finnhub 请求达到限流"
        if status_code >= 500:
            return AssetMetadataStatus.PROVIDER_UNAVAILABLE, "Finnhub 当前不可用"
        return AssetMetadataStatus.INVALID_PROVIDER_RESPONSE, "Finnhub 返回未识别的 HTTP 状态"

    @staticmethod
    def _transport_failure_message(failure: HttpTransportFailure) -> str:
        """将同步 Transport Failure 转成不泄露底层细节的消息。"""

        if failure.kind.value == "TLS_CERTIFICATE_ERROR":
            return "Finnhub TLS 证书校验失败，请检查 Python CA 根证书配置"
        if failure.kind.value == "TIMEOUT":
            return "Finnhub 请求超时"
        return "Finnhub 网络连接失败"

    @staticmethod
    def _is_supported_search_type(raw_result: Mapping[str, object]) -> bool:
        """只接收 Finnhub 明确标注的普通美股或 ETF/ETP。"""

        asset_type = raw_result.get("type")
        if not isinstance(asset_type, str):
            raise InvalidAssetMetadata("type 必须是字符串")
        return asset_type.strip().casefold() in _SUPPORTED_SEARCH_TYPES

    @staticmethod
    def _required_text(raw_result: Mapping[str, object], field_name: str) -> str:
        """拒绝 Provider 缺失或错误类型的最小必需字段。"""

        value = raw_result.get(field_name)
        if not isinstance(value, str):
            raise InvalidAssetMetadata(f"{field_name} 必须是字符串")
        return value

    def _has_credentials(self) -> bool:
        return bool(self._api_key)
