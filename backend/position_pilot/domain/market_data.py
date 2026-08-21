"""Provider-neutral Market Data Schema 与确定性校验。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from enum import StrEnum

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import normalize_ticker


class InvalidMarketData(ValueError):
    """Market Data Schema 包含无效或互相冲突的事实。"""


class MarketDataStatus(StrEnum):
    """Provider 调用的稳定结果状态。"""

    OK = "OK"
    NO_DATA = "NO_DATA"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"


class MarketDataCoverage(StrEnum):
    """行情事实覆盖的市场范围。"""

    SINGLE_EXCHANGE = "SINGLE_EXCHANGE"
    CONSOLIDATED = "CONSOLIDATED"


def _normalize_positive_decimal(value: Decimal, *, field_name: str) -> Decimal:
    """校验 Market Data 价格为有限正数。"""

    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise InvalidMarketData(f"{field_name} 必须是有限正数")
    return value


def _normalize_optional_price(value: Decimal | None, *, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _normalize_positive_decimal(value, field_name=field_name)


def _normalize_market_ticker(value: str) -> str:
    """复用 Portfolio Ticker 规则，同时保持 Market Data 异常边界。"""

    try:
        return normalize_ticker(value)
    except (InvalidPortfolioValue, AttributeError) as error:
        raise InvalidMarketData("ticker 格式无效") from error


def normalize_market_timestamp(value: datetime, *, field_name: str) -> datetime:
    """要求 Market Data 时间包含时区并统一为 UTC。"""

    if not isinstance(value, datetime):
        raise InvalidMarketData(f"{field_name} 必须是 datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidMarketData(f"{field_name} 必须包含时区")
    return value.astimezone(UTC)


def _normalize_metadata(value: str, *, field_name: str) -> str:
    return _normalize_nonempty_text(value, field_name=field_name).upper()


def _normalize_nonempty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidMarketData(f"{field_name} 必须是字符串")
    normalized = value.strip()
    if not normalized:
        raise InvalidMarketData(f"{field_name} 不能为空")
    return normalized


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """带来源和时间语义的当前行情快照。"""

    ticker: str
    last_price: Decimal
    bid_price: Decimal | None
    ask_price: Decimal | None
    last_trade_at: datetime
    quote_at: datetime | None
    source: str
    feed: str
    coverage: MarketDataCoverage
    currency: str
    is_delayed: bool
    fetched_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_market_ticker(self.ticker))
        object.__setattr__(
            self,
            "last_price",
            _normalize_positive_decimal(self.last_price, field_name="last_price"),
        )
        object.__setattr__(
            self,
            "bid_price",
            _normalize_optional_price(self.bid_price, field_name="bid_price"),
        )
        object.__setattr__(
            self,
            "ask_price",
            _normalize_optional_price(self.ask_price, field_name="ask_price"),
        )
        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.bid_price > self.ask_price
        ):
            raise InvalidMarketData("bid_price 不得高于 ask_price")
        object.__setattr__(
            self,
            "last_trade_at",
            normalize_market_timestamp(self.last_trade_at, field_name="last_trade_at"),
        )
        if self.quote_at is not None:
            object.__setattr__(
                self,
                "quote_at",
                normalize_market_timestamp(self.quote_at, field_name="quote_at"),
            )
        object.__setattr__(self, "source", _normalize_metadata(self.source, field_name="source"))
        object.__setattr__(self, "feed", _normalize_metadata(self.feed, field_name="feed"))
        object.__setattr__(
            self,
            "currency",
            _normalize_metadata(self.currency, field_name="currency"),
        )
        if len(self.currency) != 3:
            raise InvalidMarketData("currency 必须是三位代码")
        if not isinstance(self.coverage, MarketDataCoverage):
            raise InvalidMarketData("coverage 无效")
        if not isinstance(self.is_delayed, bool):
            raise InvalidMarketData("is_delayed 必须是布尔值")
        object.__setattr__(
            self,
            "fetched_at",
            normalize_market_timestamp(self.fetched_at, field_name="fetched_at"),
        )


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """单个时间区间内经过确定性校验的 OHLCV。"""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timestamp",
            normalize_market_timestamp(self.timestamp, field_name="bar timestamp"),
        )
        for field_name in ("open", "high", "low", "close"):
            value = _normalize_positive_decimal(getattr(self, field_name), field_name=field_name)
            object.__setattr__(self, field_name, value)
        if isinstance(self.volume, bool) or not isinstance(self.volume, int) or self.volume < 0:
            raise InvalidMarketData("volume 必须是非负整数")
        if self.high < max(self.open, self.low, self.close):
            raise InvalidMarketData("high 必须是 OHLC 最大值")
        if self.low > min(self.open, self.high, self.close):
            raise InvalidMarketData("low 必须是 OHLC 最小值")


@dataclass(frozen=True, slots=True)
class HistoricalBars:
    """带完整 Provider 元数据的 Historical OHLCV 集合。"""

    ticker: str
    timeframe: str
    bars: tuple[OHLCVBar, ...]
    source: str
    feed: str
    coverage: MarketDataCoverage
    currency: str
    adjustment: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_market_ticker(self.ticker))
        object.__setattr__(
            self,
            "timeframe",
            _normalize_nonempty_text(self.timeframe, field_name="timeframe"),
        )
        object.__setattr__(self, "source", _normalize_metadata(self.source, field_name="source"))
        object.__setattr__(self, "feed", _normalize_metadata(self.feed, field_name="feed"))
        object.__setattr__(
            self,
            "currency",
            _normalize_metadata(self.currency, field_name="currency"),
        )
        object.__setattr__(
            self,
            "adjustment",
            _normalize_metadata(self.adjustment, field_name="adjustment"),
        )
        if len(self.currency) != 3:
            raise InvalidMarketData("currency 必须是三位代码")
        if not isinstance(self.coverage, MarketDataCoverage):
            raise InvalidMarketData("coverage 无效")
        if not isinstance(self.bars, tuple) or not self.bars:
            raise InvalidMarketData("HistoricalBars.bars 必须是非空 tuple")
        if any(not isinstance(bar, OHLCVBar) for bar in self.bars):
            raise InvalidMarketData("bars 必须只包含 OHLCVBar")
        timestamps = [bar.timestamp for bar in self.bars]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise InvalidMarketData("bars 必须按 timestamp 严格升序且唯一")
        object.__setattr__(
            self,
            "fetched_at",
            normalize_market_timestamp(self.fetched_at, field_name="fetched_at"),
        )


@dataclass(frozen=True, slots=True)
class MarketDataResult[T]:
    """成功数据与明确失败状态的统一结构。"""

    status: MarketDataStatus
    data: T | None
    message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, MarketDataStatus):
            raise InvalidMarketData("status 无效")
        if self.status is MarketDataStatus.OK:
            if self.data is None or self.message is not None:
                raise InvalidMarketData("OK result 必须包含 data 且不能包含 message")
            return
        if self.data is not None:
            raise InvalidMarketData("Failure result 不能包含 data")
        if not isinstance(self.message, str) or not self.message.strip():
            raise InvalidMarketData("Failure result 必须包含 message")

    @classmethod
    def success(cls, data: T) -> "MarketDataResult[T]":
        """创建成功结果。"""

        return cls(status=MarketDataStatus.OK, data=data, message=None)

    @classmethod
    def failure(
        cls,
        status: MarketDataStatus,
        message: str,
    ) -> "MarketDataResult[T]":
        """创建不携带伪造数据的失败结果。"""

        if status is MarketDataStatus.OK:
            raise InvalidMarketData("failure 不能使用 OK status")
        return cls(status=status, data=None, message=message)


def decimal_from_provider(value: object, *, field_name: str) -> Decimal:
    """把 Provider 数值安全转换为 Decimal，供 Adapter 统一使用。"""

    if isinstance(value, bool) or value is None:
        raise InvalidMarketData(f"{field_name} 缺失或类型无效")
    try:
        decimal_value = Decimal(str(value))
    except (DecimalException, ValueError) as error:
        raise InvalidMarketData(f"{field_name} 不是有效数值") from error
    return _normalize_positive_decimal(decimal_value, field_name=field_name)
