"""Market Data Application Service 与 Provider Contract。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.portfolio import normalize_ticker


@dataclass(frozen=True, slots=True)
class HistoricalBarsQuery:
    """Historical Daily OHLCV 的 Provider-neutral 输入。"""

    ticker: str
    start: datetime
    end: datetime
    limit: int = 1000


class MarketDataProvider(Protocol):
    """Application 所依赖的最小 Market Data Provider 接口。"""

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]: ...

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]: ...


class MarketDataService:
    """校验调用方输入并委托单一 Market Data Provider。"""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        """按规范化 Ticker 获取结构化 Current Quote。"""

        normalized_ticker = self._normalize_ticker(ticker)
        if normalized_ticker is None:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_SYMBOL,
                "ticker 格式无效",
            )
        return self._provider.get_current_quote(normalized_ticker)

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        """校验时间范围后获取 Daily OHLCV。"""

        normalized_ticker = self._normalize_ticker(query.ticker)
        if normalized_ticker is None:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_SYMBOL,
                "ticker 格式无效",
            )
        if not self._has_timezone(query.start) or not self._has_timezone(query.end):
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_REQUEST,
                "start 与 end 必须包含时区",
            )
        if query.start >= query.end:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_REQUEST,
                "start 必须早于 end",
            )
        if query.limit < 1 or query.limit > 10_000:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_REQUEST,
                "limit 必须在 1 到 10000 之间",
            )
        return self._provider.get_historical_bars(
            HistoricalBarsQuery(
                ticker=normalized_ticker,
                start=query.start,
                end=query.end,
                limit=query.limit,
            )
        )

    @staticmethod
    def _normalize_ticker(ticker: str) -> str | None:
        try:
            return normalize_ticker(ticker)
        except (InvalidPortfolioValue, AttributeError):
            return None

    @staticmethod
    def _has_timezone(value: datetime) -> bool:
        return value.tzinfo is not None and value.utcoffset() is not None
