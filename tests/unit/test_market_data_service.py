"""Market Data Application Service 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from position_pilot.application.market_data_service import (
    HistoricalBarsQuery,
    MarketDataService,
)
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 20, tzinfo=UTC)


@dataclass(slots=True)
class FakeMarketDataProvider:
    """记录 Application 向 Provider 发出的规范化请求。"""

    quote_tickers: list[str] = field(default_factory=list)
    historical_queries: list[HistoricalBarsQuery] = field(default_factory=list)

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        self.quote_tickers.append(ticker)
        return MarketDataResult.failure(MarketDataStatus.NO_DATA, "测试无数据")

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        self.historical_queries.append(query)
        return MarketDataResult.failure(MarketDataStatus.NO_DATA, "测试无数据")


def test_service_normalizes_ticker_before_provider_call() -> None:
    """Provider 只能收到 Portfolio 已批准格式的 Ticker。"""

    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    result = service.get_current_quote(" goog ")

    assert result.status is MarketDataStatus.NO_DATA
    assert provider.quote_tickers == ["GOOG"]


def test_service_rejects_invalid_symbol_without_provider_call() -> None:
    """明显非法 Ticker 应产生稳定状态且不消耗 Provider 限额。"""

    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    result = service.get_current_quote("not/a/ticker")

    assert result.status is MarketDataStatus.INVALID_SYMBOL
    assert provider.quote_tickers == []


def test_service_validates_historical_range_and_limit() -> None:
    """非法时间范围和 limit 应在 Application 边界失败。"""

    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    reversed_range = service.get_historical_bars(
        HistoricalBarsQuery(ticker="GOOG", start=END, end=START)
    )
    excessive_limit = service.get_historical_bars(
        HistoricalBarsQuery(ticker="GOOG", start=START, end=END, limit=10_001)
    )

    assert reversed_range.status is MarketDataStatus.INVALID_REQUEST
    assert excessive_limit.status is MarketDataStatus.INVALID_REQUEST
    assert provider.historical_queries == []


def test_service_forwards_normalized_historical_query() -> None:
    """合法查询应保留时间范围并只规范化 Ticker。"""

    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    service.get_historical_bars(
        HistoricalBarsQuery(ticker=" goog ", start=START, end=END, limit=25)
    )

    assert provider.historical_queries == [
        HistoricalBarsQuery(ticker="GOOG", start=START, end=END, limit=25)
    ]
