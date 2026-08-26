"""Alpaca Market Data API v2 REST Adapter。"""

import json
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException
from enum import StrEnum
from http.client import HTTPResponse
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.config import Settings
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.market_data import (
    HistoricalBars,
    InvalidMarketData,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
    OHLCVBar,
    decimal_from_provider,
)

ALPACA_SOURCE = "ALPACA"
CURRENT_FEED = "IEX"
HISTORICAL_FEED = "SIP"
HISTORICAL_ADJUSTMENT = "ALL"
HISTORICAL_DELAY = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    """HTTP Transport 返回给 Adapter 的最小响应。"""

    status_code: int
    payload: object


class HttpTransportFailureKind(StrEnum):
    """不包含 URL、Credential 或底层异常文本的 Transport 错误类别。"""

    TLS_CERTIFICATE_ERROR = "TLS_CERTIFICATE_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"


class HttpTransportUnavailable(RuntimeError):
    """携带安全错误类别的网络、TLS、连接或读取失败。"""

    def __init__(self, kind: HttpTransportFailureKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


@dataclass(frozen=True, slots=True)
class HttpTransportFailure:
    """Adapter 可安全转换为稳定 Provider Result 的 Transport Failure。"""

    kind: HttpTransportFailureKind


class JsonHttpTransport(Protocol):
    """便于 Unit Test 替换的同步 JSON HTTP Contract。"""

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse: ...


class UrllibJsonHttpTransport:
    """只承担 HTTPS GET 与 JSON 解码的标准库 Transport。"""

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return JsonHttpResponse(
                    status_code=response.status,
                    payload=self._decode_json(response),
                )
        except HTTPError as error:
            return JsonHttpResponse(
                status_code=error.code,
                payload=self._decode_json(error),
            )
        except URLError as error:
            raise HttpTransportUnavailable(self._classify_failure(error.reason)) from error
        except (TimeoutError, OSError) as error:
            raise HttpTransportUnavailable(self._classify_failure(error)) from error

    @staticmethod
    def _decode_json(response: HTTPResponse | HTTPError) -> object:
        try:
            return json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _classify_failure(error: object) -> HttpTransportFailureKind:
        """只暴露可操作的安全类别，不向上层转发底层异常文本。"""

        if isinstance(error, ssl.SSLCertVerificationError):
            return HttpTransportFailureKind.TLS_CERTIFICATE_ERROR
        if isinstance(error, TimeoutError):
            return HttpTransportFailureKind.TIMEOUT
        return HttpTransportFailureKind.NETWORK_ERROR


class AlpacaMarketDataProvider:
    """把 Alpaca HTTP / JSON 语义转换为稳定 Market Data Result。"""

    def __init__(
        self,
        *,
        api_key_id: str | None,
        api_secret_key: str | None,
        base_url: str = "https://data.alpaca.markets",
        timeout_seconds: float = 10.0,
        transport: JsonHttpTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key_id = api_key_id.strip() if api_key_id else None
        self._api_secret_key = api_secret_key.strip() if api_secret_key else None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibJsonHttpTransport()
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        """从实时 IEX Snapshot 读取 last trade 与可选 bid / ask。"""

        if not self._has_credentials():
            return MarketDataResult.failure(
                MarketDataStatus.AUTHENTICATION_FAILED,
                "Alpaca API credentials 未配置",
            )
        response = self._get(
            f"/v2/stocks/{quote(ticker, safe='')}/snapshot",
            {"feed": CURRENT_FEED.lower(), "currency": "USD"},
        )
        if isinstance(response, HttpTransportFailure):
            return MarketDataResult.failure(
                MarketDataStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(response.kind),
            )
        failure = self._response_failure(response)
        if failure is not None:
            return MarketDataResult.failure(*failure)
        if not isinstance(response.payload, Mapping):
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                "Alpaca snapshot response 不是 JSON object",
            )

        latest_trade = response.payload.get("latestTrade")
        if latest_trade is None:
            return MarketDataResult.failure(
                MarketDataStatus.NO_DATA,
                "Alpaca 没有返回可用的 latest trade",
            )
        if not isinstance(latest_trade, Mapping):
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                "Alpaca latestTrade 格式无效",
            )

        try:
            latest_quote = response.payload.get("latestQuote")
            bid_price, ask_price, quote_at = self._parse_latest_quote(latest_quote)
            market_quote = MarketQuote(
                ticker=ticker,
                last_price=decimal_from_provider(latest_trade.get("p"), field_name="last_price"),
                bid_price=bid_price,
                ask_price=ask_price,
                last_trade_at=self._parse_timestamp(
                    latest_trade.get("t"), field_name="last_trade_at"
                ),
                quote_at=quote_at,
                source=ALPACA_SOURCE,
                feed=CURRENT_FEED,
                coverage=MarketDataCoverage.SINGLE_EXCHANGE,
                currency="USD",
                is_delayed=False,
                fetched_at=self._utc_now(),
            )
        except (InvalidMarketData, InvalidPortfolioValue) as error:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                str(error),
            )
        return MarketDataResult.success(market_quote)

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        """读取至少延迟 15 分钟的 SIP Daily OHLCV，并处理分页。"""

        if not self._has_credentials():
            return MarketDataResult.failure(
                MarketDataStatus.AUTHENTICATION_FAILED,
                "Alpaca API credentials 未配置",
            )
        now = self._utc_now()
        if query.end.astimezone(UTC) > now - HISTORICAL_DELAY:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_REQUEST,
                "Basic Plan 的 SIP historical end 必须至少落后当前 15 分钟",
            )

        raw_bars: list[object] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while len(raw_bars) < query.limit:
            parameters = {
                "timeframe": "1Day",
                "start": self._format_timestamp(query.start),
                "end": self._format_timestamp(query.end),
                "limit": str(min(10_000, query.limit - len(raw_bars))),
                "adjustment": HISTORICAL_ADJUSTMENT.lower(),
                "feed": HISTORICAL_FEED.lower(),
                "currency": "USD",
                # 先向 Provider 请求窗口内最新 N 根，再在 Adapter 边界恢复领域升序。
                "sort": "desc",
            }
            if page_token is not None:
                parameters["page_token"] = page_token
            response = self._get(
                f"/v2/stocks/{quote(query.ticker, safe='')}/bars",
                parameters,
            )
            if isinstance(response, HttpTransportFailure):
                return MarketDataResult.failure(
                    MarketDataStatus.PROVIDER_UNAVAILABLE,
                    self._transport_failure_message(response.kind),
                )
            failure = self._response_failure(response)
            if failure is not None:
                return MarketDataResult.failure(*failure)
            if not isinstance(response.payload, Mapping):
                return MarketDataResult.failure(
                    MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                    "Alpaca bars response 不是 JSON object",
                )
            page_bars = response.payload.get("bars")
            if not isinstance(page_bars, list):
                return MarketDataResult.failure(
                    MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                    "Alpaca bars 字段格式无效",
                )
            raw_bars.extend(page_bars[: query.limit - len(raw_bars)])
            next_token = response.payload.get("next_page_token")
            if next_token is None or len(raw_bars) >= query.limit:
                break
            if not isinstance(next_token, str) or not next_token or next_token in seen_tokens:
                return MarketDataResult.failure(
                    MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                    "Alpaca pagination token 格式无效或重复",
                )
            seen_tokens.add(next_token)
            page_token = next_token

        if not raw_bars:
            return MarketDataResult.failure(
                MarketDataStatus.NO_DATA,
                "指定范围没有 Historical OHLCV",
            )
        try:
            bars = tuple(reversed(tuple(self._parse_bar(raw_bar) for raw_bar in raw_bars)))
            historical_bars = HistoricalBars(
                ticker=query.ticker,
                timeframe="1Day",
                bars=bars,
                source=ALPACA_SOURCE,
                feed=HISTORICAL_FEED,
                coverage=MarketDataCoverage.CONSOLIDATED,
                currency="USD",
                adjustment=HISTORICAL_ADJUSTMENT,
                fetched_at=self._utc_now(),
            )
        except (InvalidMarketData, InvalidPortfolioValue) as error:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                str(error),
            )
        return MarketDataResult.success(historical_bars)

    def _get(
        self,
        path: str,
        parameters: Mapping[str, str],
    ) -> JsonHttpResponse | HttpTransportFailure:
        url = f"{self._base_url}{path}?{urlencode(parameters)}"
        try:
            return self._transport.get_json(
                url,
                headers={
                    "Accept": "application/json",
                    "APCA-API-KEY-ID": self._api_key_id or "",
                    "APCA-API-SECRET-KEY": self._api_secret_key or "",
                },
                timeout_seconds=self._timeout_seconds,
            )
        except HttpTransportUnavailable as error:
            return HttpTransportFailure(error.kind)

    @staticmethod
    def _transport_failure_message(kind: HttpTransportFailureKind) -> str:
        """返回可操作但不包含 Credential、URL 或底层异常内容的错误消息。"""

        if kind is HttpTransportFailureKind.TLS_CERTIFICATE_ERROR:
            return "Alpaca TLS 证书校验失败，请检查 Python CA 根证书配置"
        if kind is HttpTransportFailureKind.TIMEOUT:
            return "Alpaca 请求超时"
        return "Alpaca 网络连接失败"

    @staticmethod
    def _response_failure(
        response: JsonHttpResponse,
    ) -> tuple[MarketDataStatus, str] | None:
        status_code = response.status_code
        if 200 <= status_code < 300:
            return None
        if status_code in {400, 422}:
            status = MarketDataStatus.INVALID_REQUEST
            message = "Alpaca 拒绝了请求参数"
        elif status_code in {401, 403}:
            status = MarketDataStatus.AUTHENTICATION_FAILED
            message = "Alpaca 凭据无效或无权访问所请求 feed"
        elif status_code == 404:
            status = MarketDataStatus.NO_DATA
            message = "Alpaca 没有找到对应市场数据"
        elif status_code == 429:
            status = MarketDataStatus.RATE_LIMITED
            message = "Alpaca 请求达到限流"
        elif status_code >= 500:
            status = MarketDataStatus.PROVIDER_UNAVAILABLE
            message = "Alpaca 当前不可用"
        else:
            status = MarketDataStatus.INVALID_PROVIDER_RESPONSE
            message = "Alpaca 返回未识别的 HTTP 状态"
        return status, message

    def _has_credentials(self) -> bool:
        return bool(self._api_key_id and self._api_secret_key)

    @classmethod
    def _parse_latest_quote(
        cls,
        value: object,
    ) -> tuple[Decimal | None, Decimal | None, datetime | None]:
        if value is None:
            return None, None, None
        if not isinstance(value, Mapping):
            raise InvalidMarketData("Alpaca latestQuote 格式无效")
        bid_price = cls._parse_optional_provider_price(value.get("bp"), field_name="bid_price")
        ask_price = cls._parse_optional_provider_price(value.get("ap"), field_name="ask_price")
        quote_at = cls._parse_timestamp(value.get("t"), field_name="quote_at")
        return bid_price, ask_price, quote_at

    @staticmethod
    def _parse_optional_provider_price(value: object, *, field_name: str) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise InvalidMarketData(f"{field_name} 类型无效")
        try:
            decimal_value = Decimal(str(value))
        except (DecimalException, ValueError) as error:
            raise InvalidMarketData(f"{field_name} 不是有效数值") from error
        # Alpaca 可能用不同数值表示形式的零表示该侧 Quote 当前不可用。
        if decimal_value == 0:
            return None
        return decimal_from_provider(value, field_name=field_name)

    @classmethod
    def _parse_bar(cls, value: object) -> OHLCVBar:
        if not isinstance(value, Mapping):
            raise InvalidMarketData("Alpaca bar 格式无效")
        raw_volume = value.get("v")
        if isinstance(raw_volume, bool) or not isinstance(raw_volume, int):
            raise InvalidMarketData("volume 必须是整数")
        return OHLCVBar(
            timestamp=cls._parse_timestamp(value.get("t"), field_name="bar timestamp"),
            open=decimal_from_provider(value.get("o"), field_name="open"),
            high=decimal_from_provider(value.get("h"), field_name="high"),
            low=decimal_from_provider(value.get("l"), field_name="low"),
            close=decimal_from_provider(value.get("c"), field_name="close"),
            volume=raw_volume,
        )

    @staticmethod
    def _parse_timestamp(value: object, *, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise InvalidMarketData(f"{field_name} 缺失或类型无效")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidMarketData(f"{field_name} 格式无效") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise InvalidMarketData(f"{field_name} 必须包含时区")
        return parsed.astimezone(UTC)

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidMarketData("clock 必须返回带时区时间")
        return value.astimezone(UTC)


def create_alpaca_market_data_provider(settings: Settings) -> AlpacaMarketDataProvider:
    """从安全 Settings 创建 Alpaca Adapter，不记录或返回 Secret。"""

    api_key_id = (
        settings.alpaca_api_key_id.get_secret_value() if settings.alpaca_api_key_id else None
    )
    api_secret_key = (
        settings.alpaca_api_secret_key.get_secret_value()
        if settings.alpaca_api_secret_key
        else None
    )
    return AlpacaMarketDataProvider(
        api_key_id=api_key_id,
        api_secret_key=api_secret_key,
        base_url=str(settings.alpaca_data_base_url),
        timeout_seconds=settings.alpaca_request_timeout_seconds,
    )
