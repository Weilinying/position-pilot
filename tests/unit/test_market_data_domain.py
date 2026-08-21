"""Market Data Schema 与结果状态测试。"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from position_pilot.domain.market_data import (
    HistoricalBars,
    InvalidMarketData,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
    OHLCVBar,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_market_quote_preserves_source_coverage_and_timestamps() -> None:
    """Current Quote 必须暴露 IEX 覆盖限制与独立市场时间。"""

    quote = MarketQuote(
        ticker=" goog ",
        last_price=Decimal("201.25"),
        bid_price=Decimal("201.20"),
        ask_price=Decimal("201.30"),
        last_trade_at=NOW,
        quote_at=NOW,
        source="alpaca",
        feed="iex",
        coverage=MarketDataCoverage.SINGLE_EXCHANGE,
        currency="usd",
        is_delayed=False,
        fetched_at=NOW,
    )

    assert quote.ticker == "GOOG"
    assert quote.source == "ALPACA"
    assert quote.feed == "IEX"
    assert quote.coverage is MarketDataCoverage.SINGLE_EXCHANGE


def test_market_quote_rejects_invalid_runtime_types() -> None:
    """稳定 Schema 不得依赖调用方遵守静态 Type Hint。"""

    with pytest.raises(InvalidMarketData, match="ticker"):
        MarketQuote(
            ticker="not/a/ticker",
            last_price=Decimal("201.25"),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="ALPACA",
            feed="IEX",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )


def test_ohlcv_rejects_internally_inconsistent_prices() -> None:
    """非法 Provider OHLC 不得成为可用市场事实。"""

    with pytest.raises(InvalidMarketData, match="high"):
        OHLCVBar(
            timestamp=NOW,
            open=Decimal("100"),
            high=Decimal("99"),
            low=Decimal("98"),
            close=Decimal("100"),
            volume=10,
        )


def test_historical_bars_require_unique_ascending_timestamps() -> None:
    """Historical OHLCV 必须按市场时间严格升序。"""

    bar = OHLCVBar(
        timestamp=NOW,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=10,
    )

    with pytest.raises(InvalidMarketData, match="严格升序"):
        HistoricalBars(
            ticker="GOOG",
            timeframe="1Day",
            bars=(bar, bar),
            source="ALPACA",
            feed="SIP",
            coverage=MarketDataCoverage.CONSOLIDATED,
            currency="USD",
            adjustment="ALL",
            fetched_at=NOW,
        )


def test_historical_bars_preserve_provider_timeframe_spelling() -> None:
    """Provider-neutral Schema 应保留已批准的 Alpaca `1Day` 粒度。"""

    bar = OHLCVBar(
        timestamp=NOW,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=10,
    )

    result = HistoricalBars(
        ticker="GOOG",
        timeframe="1Day",
        bars=(bar,),
        source="ALPACA",
        feed="SIP",
        coverage=MarketDataCoverage.CONSOLIDATED,
        currency="USD",
        adjustment="ALL",
        fetched_at=NOW,
    )

    assert result.timeframe == "1Day"


def test_historical_bars_require_immutable_bar_collection() -> None:
    """Frozen Schema 不得接收仍可被调用方修改的 Bar list。"""

    bar = OHLCVBar(
        timestamp=NOW,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=10,
    )

    with pytest.raises(InvalidMarketData, match="HistoricalBars"):
        HistoricalBars(
            ticker="GOOG",
            timeframe="1Day",
            bars=[bar],  # type: ignore[arg-type]
            source="ALPACA",
            feed="SIP",
            coverage=MarketDataCoverage.CONSOLIDATED,
            currency="USD",
            adjustment="ALL",
            fetched_at=NOW,
        )


def test_result_cannot_mix_failure_with_data() -> None:
    """Failure State 不得携带可能被调用方误用的数据。"""

    with pytest.raises(InvalidMarketData, match="不能包含 data"):
        MarketDataResult(
            status=MarketDataStatus.NO_DATA,
            data="invented",
            message="没有数据",
        )


def test_result_rejects_unknown_runtime_status() -> None:
    """未知状态不得绕过稳定 Result Contract。"""

    with pytest.raises(InvalidMarketData, match="status"):
        MarketDataResult(status="UNKNOWN", data=None, message="未知")  # type: ignore[arg-type]
