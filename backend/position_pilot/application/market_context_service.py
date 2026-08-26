"""固定 SPY Daily Bars 的 Market Context Application Service。"""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.domain.market_context import (
    DAILY_TIMEFRAME,
    MARKET_PROXY_TICKER,
    MINIMUM_OBSERVATION_COUNT,
    InvalidMarketContext,
    MarketRegimeContext,
    calculate_market_regime,
)
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
)

MARKET_CONTEXT_PROXY_TICKER = "SPY"
MARKET_CONTEXT_LOOKBACK_DAYS = 90
MARKET_CONTEXT_LIMIT = 60
MARKET_CONTEXT_END_LAG = timedelta(minutes=15)
MARKET_CONTEXT_MAX_STALENESS_DAYS = 7
_NEW_YORK = ZoneInfo("America/New_York")
_REGULAR_SESSION_CLOSE = time(16, 0)


class MarketContextDataReader(Protocol):
    """Market Context 只依赖 Historical Daily Bars 的最小接口。"""

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]: ...


class MarketContextService:
    """锁定 Proxy、窗口和阈值，返回可追踪的确定性 Regime。"""

    def __init__(
        self,
        market_data: MarketContextDataReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._market_data = market_data
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]:
        """获取固定 SPY Daily Bars，并用 V1 Heuristic 计算 Market Regime。"""

        current_time = self._clock()
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_REQUEST,
                "Market Context clock 必须包含时区",
            )
        end = current_time.astimezone(UTC) - MARKET_CONTEXT_END_LAG
        result = self._market_data.get_historical_bars(
            HistoricalBarsQuery(
                ticker=MARKET_CONTEXT_PROXY_TICKER,
                start=end - timedelta(days=MARKET_CONTEXT_LOOKBACK_DAYS),
                end=end,
                limit=MARKET_CONTEXT_LIMIT,
            )
        )
        if result.status is not MarketDataStatus.OK:
            assert result.message is not None
            return MarketDataResult.failure(result.status, result.message)

        historical_bars = result.data
        assert historical_bars is not None
        if (
            historical_bars.ticker != MARKET_PROXY_TICKER
            or historical_bars.timeframe != DAILY_TIMEFRAME
        ):
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                "Market Context Provider 返回了非 SPY 1Day 数据",
            )
        if (
            historical_bars.source != "ALPACA"
            or historical_bars.feed != "SIP"
            or historical_bars.coverage is not MarketDataCoverage.CONSOLIDATED
            or historical_bars.adjustment != "ALL"
            or historical_bars.currency != "USD"
        ):
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                (
                    "Market Context Provider 返回了不符合 "
                    "SPY/ALPACA/SIP/CONSOLIDATED/ALL/USD 语义的数据"
                ),
            )
        completed_bars = tuple(
            bar
            for bar in historical_bars.bars
            if _is_completed_daily_bar(bar.timestamp, query_end=end)
        )
        if len(completed_bars) < MINIMUM_OBSERVATION_COUNT:
            return MarketDataResult.failure(
                MarketDataStatus.NO_DATA,
                "Market Regime 至少需要 21 根 completed SPY Daily Bars",
            )
        if _is_obviously_stale(completed_bars[-1].timestamp, query_end=end):
            return MarketDataResult.failure(
                MarketDataStatus.NO_DATA,
                "最新 completed SPY Daily Bar 已超过 7 个日历日，Market Regime 保持 UNKNOWN",
            )
        completed_history = HistoricalBars(
            ticker=historical_bars.ticker,
            timeframe=historical_bars.timeframe,
            bars=completed_bars,
            source=historical_bars.source,
            feed=historical_bars.feed,
            coverage=historical_bars.coverage,
            currency=historical_bars.currency,
            adjustment=historical_bars.adjustment,
            fetched_at=historical_bars.fetched_at,
        )
        try:
            context = calculate_market_regime(completed_history)
        except InvalidMarketContext as error:
            return MarketDataResult.failure(
                MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                f"Market Context 输入不满足确定性边界：{error}",
            )
        return MarketDataResult.success(context)


def _is_completed_daily_bar(timestamp: datetime, *, query_end: datetime) -> bool:
    """按纽约常规收盘时间保守排除仍可能变化的当前 Session Daily Bar。"""

    return timestamp.astimezone(_NEW_YORK).date() <= _latest_completed_session_date(query_end)


def _is_obviously_stale(timestamp: datetime, *, query_end: datetime) -> bool:
    """仅拒绝明显陈旧数据，并容纳正常周末和交易所假期。"""

    latest_bar_date = timestamp.astimezone(_NEW_YORK).date()
    age_days = (_latest_completed_session_date(query_end) - latest_bar_date).days
    return age_days > MARKET_CONTEXT_MAX_STALENESS_DAYS


def _latest_completed_session_date(query_end: datetime) -> date:
    """返回按纽约常规收盘时间推导的最近可完成 Session 日期上界。"""

    market_end = query_end.astimezone(_NEW_YORK)
    latest_completed_session_date = market_end.date()
    if market_end.time() < _REGULAR_SESSION_CLOSE:
        latest_completed_session_date -= timedelta(days=1)
    return latest_completed_session_date
