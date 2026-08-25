"""Alpaca News API Adapter。"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

from position_pilot.application.news_service import NewsQuery
from position_pilot.config import Settings
from position_pilot.domain.news import NewsArticle, NewsResult, NewsStatus, RecentNews
from position_pilot.integrations.alpaca_market_data import (
    HttpTransportFailure,
    HttpTransportFailureKind,
    HttpTransportUnavailable,
    JsonHttpResponse,
    JsonHttpTransport,
    UrllibJsonHttpTransport,
)

ALPACA_SOURCE = "ALPACA"


class AlpacaNewsProvider:
    """把 Alpaca News HTTP / JSON 语义转换为稳定的 News Result。"""

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

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        """按固定查询读取 Alpaca News，且永不请求文章正文。"""

        if not self._has_credentials():
            return NewsResult.failure(
                NewsStatus.AUTHENTICATION_FAILED,
                "Alpaca API credentials 未配置",
            )
        response = self._get(
            "/v1beta1/news",
            {
                "symbols": query.ticker,
                "start": self._format_timestamp(query.start),
                "end": self._format_timestamp(query.end),
                "sort": "desc",
                "limit": str(query.limit),
                "include_content": "false",
            },
        )
        if isinstance(response, HttpTransportFailure):
            return NewsResult.failure(
                NewsStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(response.kind),
            )
        failure = self._response_failure(response)
        if failure is not None:
            return NewsResult.failure(*failure)
        if not isinstance(response.payload, Mapping):
            return NewsResult.failure(
                NewsStatus.INVALID_PROVIDER_RESPONSE,
                "Alpaca news response 不是 JSON object",
            )
        raw_news = response.payload.get("news")
        if not isinstance(raw_news, list):
            return NewsResult.failure(
                NewsStatus.INVALID_PROVIDER_RESPONSE,
                "Alpaca news 字段格式无效",
            )
        if not raw_news:
            return NewsResult.failure(
                NewsStatus.NO_NEWS_FOUND,
                "指定范围没有相关新闻",
            )
        if len(raw_news) > query.limit:
            return NewsResult.failure(
                NewsStatus.INVALID_PROVIDER_RESPONSE,
                "Alpaca 返回的文章数量超过请求上限",
            )
        try:
            articles: list[NewsArticle] = []
            for raw_article in raw_news:
                if not self._includes_ticker(raw_article, query.ticker):
                    continue
                article = self._parse_article(raw_article)
                if not query.start <= article.updated_at <= query.end:
                    raise ValueError("Alpaca 返回了查询窗口外的新闻")
                articles.append(article)
            if not articles:
                return NewsResult.failure(
                    NewsStatus.NO_NEWS_FOUND,
                    "指定范围没有包含所请求 ticker 的新闻",
                )
            recent_news = RecentNews(
                ticker=query.ticker,
                articles=tuple(articles),
                provider=ALPACA_SOURCE,
                fetched_at=self._utc_now(),
            )
        except (TypeError, ValueError) as error:
            return NewsResult.failure(
                NewsStatus.INVALID_PROVIDER_RESPONSE,
                str(error),
            )
        return NewsResult.success(recent_news)

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
        """返回不泄露 URL、Credential 或底层异常的 Transport 错误。"""

        if kind is HttpTransportFailureKind.TLS_CERTIFICATE_ERROR:
            return "Alpaca TLS 证书校验失败，请检查 Python CA 根证书配置"
        if kind is HttpTransportFailureKind.TIMEOUT:
            return "Alpaca 请求超时"
        return "Alpaca 网络连接失败"

    @staticmethod
    def _response_failure(
        response: JsonHttpResponse,
    ) -> tuple[NewsStatus, str] | None:
        status_code = response.status_code
        if 200 <= status_code < 300:
            return None
        if status_code in {400, 422}:
            return NewsStatus.INVALID_REQUEST, "Alpaca 拒绝了请求参数"
        if status_code in {401, 403}:
            return NewsStatus.AUTHENTICATION_FAILED, "Alpaca 凭据无效或无权访问 News"
        if status_code == 404:
            return NewsStatus.INVALID_PROVIDER_RESPONSE, "Alpaca News Endpoint 不可用"
        if status_code == 429:
            return NewsStatus.RATE_LIMITED, "Alpaca 请求达到限流"
        if status_code >= 500:
            return NewsStatus.PROVIDER_UNAVAILABLE, "Alpaca 当前不可用"
        return NewsStatus.INVALID_PROVIDER_RESPONSE, "Alpaca 返回未识别的 HTTP 状态"

    @staticmethod
    def _includes_ticker(value: object, ticker: str) -> bool:
        """先严格校验 symbols，再只保留 Alpaca 明确归因于查询标的的文章。"""

        if not isinstance(value, Mapping):
            raise ValueError("Alpaca news item 格式无效")
        raw_symbols = value.get("symbols")
        if not isinstance(raw_symbols, list) or not all(
            isinstance(symbol, str) and symbol.strip() for symbol in raw_symbols
        ):
            raise ValueError("Alpaca news symbols 字段格式无效")
        return ticker in {symbol.strip().upper() for symbol in raw_symbols}

    @staticmethod
    def _parse_article(value: object) -> NewsArticle:
        if not isinstance(value, Mapping):
            raise ValueError("Alpaca news item 格式无效")
        raw_symbols = value.get("symbols")
        if not isinstance(raw_symbols, list):
            raise ValueError("Alpaca news symbols 字段格式无效")
        symbols = tuple(
            AlpacaNewsProvider._required_text(symbol, field_name="news symbol").upper()
            for symbol in raw_symbols
        )
        return NewsArticle(
            article_id=AlpacaNewsProvider._parse_article_id(value.get("id")),
            headline=AlpacaNewsProvider._required_text(
                value.get("headline"), field_name="news headline"
            ),
            summary=AlpacaNewsProvider._optional_text(
                value.get("summary"), field_name="news summary"
            ),
            author=AlpacaNewsProvider._optional_text(value.get("author"), field_name="news author"),
            url=AlpacaNewsProvider._required_text(value.get("url"), field_name="news url"),
            source=AlpacaNewsProvider._required_text(
                value.get("source"), field_name="news source"
            ).upper(),
            symbols=symbols,
            created_at=AlpacaNewsProvider._parse_timestamp(
                value.get("created_at"), field_name="news created_at"
            ),
            updated_at=AlpacaNewsProvider._parse_timestamp(
                value.get("updated_at"), field_name="news updated_at"
            ),
        )

    @staticmethod
    def _required_text(value: object, *, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 缺失或类型无效")
        return value.strip()

    @staticmethod
    def _parse_article_id(value: object) -> str:
        """Alpaca 的文章 ID 可以是 JSON string 或整数，领域统一保存为字符串。"""

        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return str(value)
        return AlpacaNewsProvider._required_text(value, field_name="news id")

    @staticmethod
    def _optional_text(value: object, *, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field_name} 类型无效")
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _parse_timestamp(value: object, *, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} 缺失或类型无效")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field_name} 格式无效") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} 必须包含时区")
        return parsed.astimezone(UTC)

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _has_credentials(self) -> bool:
        return bool(self._api_key_id and self._api_secret_key)

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock 必须返回带时区时间")
        return value.astimezone(UTC)


def create_alpaca_news_provider(settings: Settings) -> AlpacaNewsProvider:
    """从安全 Settings 创建 Alpaca News Adapter，不记录或返回 Secret。"""

    api_key_id = (
        settings.alpaca_api_key_id.get_secret_value() if settings.alpaca_api_key_id else None
    )
    api_secret_key = (
        settings.alpaca_api_secret_key.get_secret_value()
        if settings.alpaca_api_secret_key
        else None
    )
    return AlpacaNewsProvider(
        api_key_id=api_key_id,
        api_secret_key=api_secret_key,
        base_url=str(settings.alpaca_data_base_url),
        timeout_seconds=settings.alpaca_request_timeout_seconds,
    )
