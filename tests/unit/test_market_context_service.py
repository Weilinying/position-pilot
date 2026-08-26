"""MarketContextService 固定查询与 Failure Mapping 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from position_pilot.application.market_context_service import (
    MARKET_CONTEXT_END_LAG,
    MARKET_CONTEXT_LIMIT,
    MARKET_CONTEXT_LOOKBACK_DAYS,
    MarketContextService,
)
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.domain.market_context import MarketRegime
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    OHLCVBar,
)

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakeMarketData:
    """记录固定查询并返回脚本化 Historical Result。"""

    result: MarketDataResult[HistoricalBars]
    queries: list[HistoricalBarsQuery] = field(default_factory=list)

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        self.queries.append(query)
        return self.result


def _history(
    *,
    ticker: str = "SPY",
    timeframe: str = "1Day",
    count: int = 21,
    latest_timestamp: datetime | None = None,
    source: str = "ALPACA",
    feed: str = "SIP",
    coverage: MarketDataCoverage = MarketDataCoverage.CONSOLIDATED,
    currency: str = "USD",
    adjustment: str = "ALL",
) -> HistoricalBars:
    latest = latest_timestamp or (NOW - timedelta(days=1))
    bars = tuple(
        OHLCVBar(
            timestamp=latest - timedelta(days=count - 1 - index),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=1_000,
        )
        for index in range(count)
    )
    return HistoricalBars(
        ticker=ticker,
        timeframe=timeframe,
        bars=bars,
        source=source,
        feed=feed,
        coverage=coverage,
        currency=currency,
        adjustment=adjustment,
        fetched_at=NOW,
    )


def test_uses_fixed_proxy_window_limit_and_calculates_context() -> None:
    """调用方不能修改 SPY、时间窗口、Bar 数量或阈值。"""

    market_data = FakeMarketData(MarketDataResult.success(_history()))
    service = MarketContextService(market_data, clock=lambda: NOW)

    result = service.get_current_market_context()

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert result.data.regime is MarketRegime.NORMAL
    assert market_data.queries == [
        HistoricalBarsQuery(
            ticker="SPY",
            start=NOW - MARKET_CONTEXT_END_LAG - timedelta(days=MARKET_CONTEXT_LOOKBACK_DAYS),
            end=NOW - MARKET_CONTEXT_END_LAG,
            limit=MARKET_CONTEXT_LIMIT,
        )
    ]


@pytest.mark.parametrize(
    "status",
    [
        MarketDataStatus.NO_DATA,
        MarketDataStatus.INVALID_SYMBOL,
        MarketDataStatus.INVALID_REQUEST,
        MarketDataStatus.AUTHENTICATION_FAILED,
        MarketDataStatus.RATE_LIMITED,
        MarketDataStatus.PROVIDER_UNAVAILABLE,
        MarketDataStatus.INVALID_PROVIDER_RESPONSE,
    ],
)
def test_preserves_market_data_failure_taxonomy(status: MarketDataStatus) -> None:
    """Provider Failure 不得被折叠为通用 UNKNOWN。"""

    market_data = FakeMarketData(MarketDataResult.failure(status, "固定失败"))

    result = MarketContextService(market_data, clock=lambda: NOW).get_current_market_context()

    assert result.status is status
    assert result.message == "固定失败"


def test_insufficient_completed_bars_is_no_data() -> None:
    """成功响应但样本不足是局部 NO_DATA，不是 Provider Failure。"""

    market_data = FakeMarketData(MarketDataResult.success(_history(count=20)))

    result = MarketContextService(market_data, clock=lambda: NOW).get_current_market_context()

    assert result.status is MarketDataStatus.NO_DATA
    assert result.data is None
    assert result.message is not None and "21" in result.message


@pytest.mark.parametrize(
    ("ticker", "timeframe"),
    [("QQQ", "1Day"), ("SPY", "1Hour")],
)
def test_incompatible_success_payload_is_invalid_provider_response(
    ticker: str,
    timeframe: str,
) -> None:
    """内部固定查询不可能产生的代理或粒度必须视为非法响应。"""

    market_data = FakeMarketData(
        MarketDataResult.success(_history(ticker=ticker, timeframe=timeframe))
    )

    result = MarketContextService(market_data, clock=lambda: NOW).get_current_market_context()

    assert result.status is MarketDataStatus.INVALID_PROVIDER_RESPONSE
    assert result.data is None
    assert result.message is not None and "SPY 1Day" in result.message


def test_wrong_proxy_is_invalid_even_when_sample_is_also_insufficient() -> None:
    """非法成功 Payload 不得被样本数量检查掩盖。"""

    market_data = FakeMarketData(MarketDataResult.success(_history(ticker="QQQ", count=20)))

    result = MarketContextService(market_data, clock=lambda: NOW).get_current_market_context()

    assert result.status is MarketDataStatus.INVALID_PROVIDER_RESPONSE
    assert result.message is not None and "SPY 1Day" in result.message


@pytest.mark.parametrize(
    "history",
    [
        pytest.param(_history(source="OTHER"), id="source"),
        pytest.param(_history(feed="IEX"), id="feed"),
        pytest.param(
            _history(coverage=MarketDataCoverage.SINGLE_EXCHANGE),
            id="coverage",
        ),
        pytest.param(_history(adjustment="RAW"), id="adjustment"),
        pytest.param(_history(currency="EUR"), id="currency"),
    ],
)
def test_incompatible_market_context_semantics_are_invalid_provider_response(
    history: HistoricalBars,
) -> None:
    """固定 SPY Market Context 的数据语义必须在 Service 边界校验。"""

    market_data = FakeMarketData(MarketDataResult.success(history))

    result = MarketContextService(market_data, clock=lambda: NOW).get_current_market_context()

    assert result.status is MarketDataStatus.INVALID_PROVIDER_RESPONSE
    assert result.data is None
    assert result.message is not None and "语义" in result.message


def test_excludes_current_session_bar_during_market_hours() -> None:
    """交易时段内的当日聚合 Bar 不得冒充 completed Daily Bar。"""

    during_market = datetime(2026, 8, 26, 18, 0, tzinfo=UTC)
    history = _history(
        count=22,
        latest_timestamp=datetime(2026, 8, 26, 4, 0, tzinfo=UTC),
    )
    market_data = FakeMarketData(MarketDataResult.success(history))

    result = MarketContextService(
        market_data,
        clock=lambda: during_market,
    ).get_current_market_context()

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert result.data.period_end.astimezone(UTC).date() < during_market.date()


def test_includes_current_session_bar_after_regular_close_and_lag() -> None:
    """常规收盘并满足 15 分钟延迟后可以纳入当日 Daily Bar。"""

    after_market = datetime(2026, 8, 26, 21, 0, tzinfo=UTC)
    history = _history(
        count=22,
        latest_timestamp=datetime(2026, 8, 26, 4, 0, tzinfo=UTC),
    )
    market_data = FakeMarketData(MarketDataResult.success(history))

    result = MarketContextService(
        market_data,
        clock=lambda: after_market,
    ).get_current_market_context()

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert result.data.period_end == history.bars[-1].timestamp


def test_naive_clock_fails_before_provider_call() -> None:
    """固定窗口需要绝对时间，naive clock 不得进入 Provider。"""

    market_data = FakeMarketData(MarketDataResult.success(_history()))
    service = MarketContextService(
        market_data,
        clock=lambda: datetime(2026, 8, 26, 8, 0),
    )

    result = service.get_current_market_context()

    assert result.status is MarketDataStatus.INVALID_REQUEST
    assert market_data.queries == []
