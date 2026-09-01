"""Massive Asset Metadata API 的 Provider Adapter。"""

import logging
from collections.abc import Mapping
from time import monotonic
from urllib.parse import quote, urlencode

from position_pilot.application.asset_metadata_service import AssetMetadataProvider
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetStatus,
    AssetValidationQuery,
    AssetValidationResult,
    InvalidAssetMetadata,
)
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailure,
    HttpTransportUnavailable,
    JsonHttpResponse,
    JsonHttpTransport,
    UrllibJsonHttpTransport,
)

MASSIVE_SOURCE = "MASSIVE"
MASSIVE_DEFAULT_BASE_URL = "https://api.massive.com"
logger = logging.getLogger(__name__)


class MassiveAssetMetadataProvider(AssetMetadataProvider):
    """将 Massive Reference Data 映射为最小 Provider-neutral Asset Contract。"""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = MASSIVE_DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        transport: JsonHttpTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibJsonHttpTransport()

    def search(self, query: AssetSearchQuery) -> AssetSearchResult:
        """搜索美国股票与 ETF，并只输出当前可用的候选。"""

        if not isinstance(query, AssetSearchQuery):
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_REQUEST,
                "Massive search query 类型无效",
            )
        if not self._has_credentials():
            return AssetSearchResult.failure(
                AssetMetadataStatus.AUTHENTICATION_FAILED,
                "Massive API credential 未配置",
            )

        response = self._get(
            "/v3/reference/tickers",
            {
                "search": query.query,
                "market": "stocks",
                "locale": "us",
                "active": "true",
                "limit": str(query.limit),
            },
        )
        if isinstance(response, HttpTransportFailure):
            return AssetSearchResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(response),
            )
        failure = self._response_failure(response, not_found_is_no_match=False)
        if failure is not None:
            return AssetSearchResult.failure(*failure)

        payload = self._mapping_payload(response)
        if payload is None:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive response 不是有效的 JSON object",
            )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive search response 的 results 格式无效",
            )
        if not raw_results:
            return AssetSearchResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Massive 没有找到匹配 Asset",
            )

        candidates: list[AssetIdentity] = []
        try:
            for raw_result in raw_results:
                if not isinstance(raw_result, Mapping):
                    return AssetSearchResult.failure(
                        AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                        "Massive search result 不是 JSON object",
                    )
                if not self._is_supported_us_asset(raw_result):
                    continue
                candidates.append(self._parse_asset(raw_result))
        except InvalidAssetMetadata as error:
            return AssetSearchResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                f"Massive Asset 字段格式无效: {error}",
            )

        if not candidates:
            return AssetSearchResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "没有找到可用于 PositionPilot 的美国股票或 ETF",
            )
        return AssetSearchResult.success(tuple(candidates))

    def get_exact(self, query: AssetValidationQuery) -> AssetValidationResult:
        """通过单 ticker详情 Endpoint 验证一个 Provider canonical symbol。"""

        if not isinstance(query, AssetValidationQuery):
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_REQUEST,
                "Massive validation query 类型无效",
            )
        if not self._has_credentials():
            return AssetValidationResult.failure(
                AssetMetadataStatus.AUTHENTICATION_FAILED,
                "Massive API credential 未配置",
            )

        response = self._get(
            f"/v3/reference/tickers/{quote(query.symbol, safe='')}",
            {},
        )
        if isinstance(response, HttpTransportFailure):
            return AssetValidationResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(response),
            )
        failure = self._response_failure(response, not_found_is_no_match=True)
        if failure is not None:
            return AssetValidationResult.failure(*failure)

        payload = self._mapping_payload(response)
        if payload is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive response 不是有效的 JSON object",
            )
        if "results" not in payload:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive ticker detail 缺少 results 字段",
            )
        raw_result = payload["results"]
        if raw_result is None:
            return AssetValidationResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Massive 没有找到对应 Asset",
            )
        if not isinstance(raw_result, Mapping):
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive ticker detail 的 results 格式无效",
            )
        try:
            if not self._is_supported_us_asset(raw_result):
                return AssetValidationResult.failure(
                    AssetMetadataStatus.NO_MATCH,
                    "Asset 不是可用的美国股票或 ETF",
                )
            asset = self._parse_asset(raw_result)
        except InvalidAssetMetadata as error:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                f"Massive Asset 字段格式无效: {error}",
            )
        if asset.canonical_symbol != query.symbol:
            return AssetValidationResult.failure(
                AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                "Massive exact response 的 canonical symbol 与请求不一致",
            )
        return AssetValidationResult.success(asset)

    def _get(
        self,
        path: str,
        parameters: Mapping[str, str],
    ) -> JsonHttpResponse | HttpTransportFailure:
        request_parameters = dict(parameters)
        request_parameters["apiKey"] = self._api_key or ""
        url = f"{self._base_url}{path}?{urlencode(request_parameters)}"
        started_at = monotonic()
        try:
            response = self._transport.get_json(
                url,
                headers={"Accept": "application/json"},
                timeout_seconds=self._timeout_seconds,
            )
            logger.info(
                "asset_metadata_provider_call",
                extra={
                    "provider": MASSIVE_SOURCE,
                    "http_status": response.status_code,
                    "latency_ms": round((monotonic() - started_at) * 1000, 2),
                },
            )
            return response
        except HttpTransportUnavailable as error:
            logger.warning(
                "asset_metadata_provider_failure",
                extra={
                    "provider": MASSIVE_SOURCE,
                    "failure_kind": error.kind.value,
                    "latency_ms": round((monotonic() - started_at) * 1000, 2),
                },
            )
            return HttpTransportFailure(error.kind)

    @staticmethod
    def _mapping_payload(
        response: JsonHttpResponse,
    ) -> Mapping[str, object] | None:
        if not isinstance(response.payload, Mapping):
            return None
        provider_status = response.payload.get("status")
        if provider_status is not None and provider_status != "OK":
            return None
        return response.payload

    @staticmethod
    def _response_failure(
        response: JsonHttpResponse,
        *,
        not_found_is_no_match: bool,
    ) -> tuple[AssetMetadataStatus, str] | None:
        status_code = response.status_code
        if 200 <= status_code < 300:
            return None
        if status_code in {400, 422}:
            return AssetMetadataStatus.INVALID_REQUEST, "Massive 拒绝了请求参数"
        if status_code in {401, 403}:
            return AssetMetadataStatus.AUTHENTICATION_FAILED, "Massive credential 无效或无权访问"
        if status_code == 404 and not_found_is_no_match:
            return AssetMetadataStatus.NO_MATCH, "Massive 没有找到对应 Asset"
        if status_code == 404:
            return AssetMetadataStatus.INVALID_PROVIDER_RESPONSE, "Massive Search Endpoint 不可用"
        if status_code == 429:
            return AssetMetadataStatus.RATE_LIMITED, "Massive 请求达到限流"
        if status_code >= 500:
            return AssetMetadataStatus.PROVIDER_UNAVAILABLE, "Massive 当前不可用"
        return AssetMetadataStatus.INVALID_PROVIDER_RESPONSE, "Massive 返回未识别的 HTTP 状态"

    @staticmethod
    def _transport_failure_message(failure: HttpTransportFailure) -> str:
        """将同步 Transport Failure 转成不泄露底层细节的消息。"""

        kind = failure.kind.value
        if kind == "TLS_CERTIFICATE_ERROR":
            return "Massive TLS 证书校验失败，请检查 Python CA 根证书配置"
        if kind == "TIMEOUT":
            return "Massive 请求超时"
        return "Massive 网络连接失败"

    @staticmethod
    def _is_supported_us_asset(raw_result: Mapping[str, object]) -> bool:
        """在 Adapter 边界过滤到美国股票市场且仍 active 的记录。"""

        locale = raw_result.get("locale")
        market = raw_result.get("market")
        active = raw_result.get("active")
        if (
            not isinstance(locale, str)
            or not isinstance(market, str)
            or not isinstance(active, bool)
        ):
            raise InvalidAssetMetadata("locale、market 或 active 字段格式无效")
        return locale.casefold() == "us" and market.casefold() == "stocks" and active is True

    @staticmethod
    def _parse_asset(raw_result: Mapping[str, object]) -> AssetIdentity:
        """只映射 Selector 真实需要的四个字段。"""

        return AssetIdentity(
            canonical_symbol=MassiveAssetMetadataProvider._required_text(raw_result, "ticker"),
            display_name=MassiveAssetMetadataProvider._required_text(raw_result, "name"),
            exchange=MassiveAssetMetadataProvider._required_text(raw_result, "primary_exchange"),
            status=AssetStatus.ACTIVE,
        )

    @staticmethod
    def _required_text(raw_result: Mapping[str, object], field_name: str) -> str:
        """拒绝 Provider 缺失或错误类型的最小必需字段。"""

        value = raw_result.get(field_name)
        if not isinstance(value, str):
            raise InvalidAssetMetadata(f"{field_name} 必须是字符串")
        return value

    def _has_credentials(self) -> bool:
        return bool(self._api_key)
