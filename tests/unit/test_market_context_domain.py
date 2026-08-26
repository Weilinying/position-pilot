"""Market Regime 确定性规则测试。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from position_pilot.domain.market_context import (
    REGIME_DISCLAIMER,
    REGIME_METHODOLOGY,
    REGIME_VERSION,
    InvalidMarketContext,
    MarketRegime,
    calculate_market_regime,
    classify_market_regime,
)
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    OHLCVBar,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _historical_bars(
    closes: list[Decimal],
    *,
    ticker: str = "SPY",
    timeframe: str = "1Day",
) -> HistoricalBars:
    bars = tuple(
        OHLCVBar(
            timestamp=NOW + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=100,
        )
        for index, close in enumerate(closes)
    )
    return HistoricalBars(
        ticker=ticker,
        timeframe=timeframe,
        bars=bars,
        source="alpaca",
        feed="sip",
        coverage=MarketDataCoverage.CONSOLIDATED,
        currency="usd",
        adjustment="all",
        fetched_at=NOW,
    )


def _closes_with_final_value(final_value: Decimal) -> list[Decimal]:
    return [Decimal("100"), Decimal("100")] + [final_value] * 19


@pytest.mark.parametrize(
    ("final_value", "regime", "rule_id"),
    [
        (Decimal("95.0000"), MarketRegime.ELEVATED_VOLATILITY, "ELEVATED_DRAWDOWN_LTE_NEGATIVE_5"),
        (Decimal("90.0000"), MarketRegime.HIGH_STRESS, "HIGH_DRAWDOWN_LTE_NEGATIVE_10"),
        (Decimal("85.0000"), MarketRegime.EXTREME_STRESS, "EXTREME_DRAWDOWN_LTE_NEGATIVE_15"),
    ],
)
def test_drawdown_threshold_boundaries_select_the_matching_regime(
    final_value: Decimal,
    regime: MarketRegime,
    rule_id: str,
) -> None:
    """量化后的阈值等值必须稳定触发对应级别。"""

    result = calculate_market_regime(_historical_bars(_closes_with_final_value(final_value)))

    assert result.regime is regime
    assert result.twenty_session_drawdown_pct == (final_value - Decimal("100.0000"))
    assert rule_id in result.triggered_rule_ids


@pytest.mark.parametrize(
    ("five_day_return", "drawdown", "volatility", "regime", "rule_id"),
    [
        (
            Decimal("0"),
            Decimal("0"),
            Decimal("25.0000"),
            MarketRegime.ELEVATED_VOLATILITY,
            "ELEVATED_VOLATILITY_GTE_25",
        ),
        (
            Decimal("0"),
            Decimal("0"),
            Decimal("40.0000"),
            MarketRegime.HIGH_STRESS,
            "HIGH_VOLATILITY_GTE_40",
        ),
        (
            Decimal("0"),
            Decimal("0"),
            Decimal("60.0000"),
            MarketRegime.EXTREME_STRESS,
            "EXTREME_VOLATILITY_GTE_60",
        ),
        (
            Decimal("-3.0000"),
            Decimal("0"),
            Decimal("0"),
            MarketRegime.ELEVATED_VOLATILITY,
            "ELEVATED_RETURN_5D_LTE_NEGATIVE_3",
        ),
        (
            Decimal("-6.0000"),
            Decimal("0"),
            Decimal("0"),
            MarketRegime.HIGH_STRESS,
            "HIGH_RETURN_5D_LTE_NEGATIVE_6",
        ),
        (
            Decimal("-10.0000"),
            Decimal("0"),
            Decimal("0"),
            MarketRegime.EXTREME_STRESS,
            "EXTREME_RETURN_5D_LTE_NEGATIVE_10",
        ),
    ],
)
def test_all_volatility_and_return_threshold_boundaries_are_inclusive(
    five_day_return: Decimal,
    drawdown: Decimal,
    volatility: Decimal,
    regime: MarketRegime,
    rule_id: str,
) -> None:
    """所有获批阈值应基于已量化值以包含边界的方式判定。"""

    result, rule_ids = classify_market_regime(
        five_session_return_pct=five_day_return,
        twenty_session_drawdown_pct=drawdown,
        twenty_session_annualized_volatility_pct=volatility,
    )

    assert result is regime
    assert rule_ids == (rule_id,)


def test_highest_severity_only_preserves_its_own_triggered_rule_ids() -> None:
    """同时命中多个级别时，不得把较低级别规则伪装为最终触发原因。"""

    result = calculate_market_regime(_historical_bars(_closes_with_final_value(Decimal("85"))))

    assert result.regime is MarketRegime.EXTREME_STRESS
    assert result.triggered_rule_ids == ("EXTREME_DRAWDOWN_LTE_NEGATIVE_15",)


def test_same_severity_preserves_all_triggered_rule_ids() -> None:
    """同一最高级别命中的原始规则必须全部可追踪。"""

    regime, rule_ids = classify_market_regime(
        five_session_return_pct=Decimal("-10.0000"),
        twenty_session_drawdown_pct=Decimal("-15.0000"),
        twenty_session_annualized_volatility_pct=Decimal("60.0000"),
    )

    assert regime is MarketRegime.EXTREME_STRESS
    assert rule_ids == (
        "EXTREME_VOLATILITY_GTE_60",
        "EXTREME_DRAWDOWN_LTE_NEGATIVE_15",
        "EXTREME_RETURN_5D_LTE_NEGATIVE_10",
    )


def test_flat_prices_produce_normal_regime_and_zero_volatility() -> None:
    """无价格变化时年化 sample volatility 必须为零。"""

    result = calculate_market_regime(_historical_bars([Decimal("100")] * 21))

    assert result.regime is MarketRegime.NORMAL
    assert result.five_session_return_pct == Decimal("0.0000")
    assert result.twenty_session_drawdown_pct == Decimal("0.0000")
    assert result.twenty_session_annualized_volatility_pct == Decimal("0.0000")
    assert result.triggered_rule_ids == ()


def test_result_quantizes_metrics_and_preserves_last_twenty_one_bars_metadata() -> None:
    """指标、计算窗口及 Provider Metadata 必须可追踪且不受额外历史影响。"""

    closes = [Decimal("90")] * 5 + [Decimal("100")] * 20 + [Decimal("100.123456")]
    historical_bars = _historical_bars(closes)

    result = calculate_market_regime(historical_bars)

    assert result.five_session_return_pct == Decimal("0.1235")
    assert result.twenty_session_drawdown_pct == Decimal("0.0000")
    assert result.observation_count == 21
    assert result.period_start == historical_bars.bars[5].timestamp
    assert result.period_end == historical_bars.bars[-1].timestamp
    assert result.source == "ALPACA"
    assert result.feed == "SIP"
    assert result.coverage is MarketDataCoverage.CONSOLIDATED
    assert result.currency == "USD"
    assert result.adjustment == "ALL"
    assert result.fetched_at == NOW
    assert result.methodology == REGIME_METHODOLOGY
    assert result.version == REGIME_VERSION
    assert result.disclaimer == REGIME_DISCLAIMER


def test_constant_one_percent_returns_have_known_metrics() -> None:
    """独立金样覆盖 5-session Return、Drawdown 与 Sample Volatility。"""

    closes = [Decimal("100") * (Decimal("1.01") ** index) for index in range(21)]

    result = calculate_market_regime(_historical_bars(closes))

    assert result.five_session_return_pct == Decimal("5.1010")
    assert result.twenty_session_drawdown_pct == Decimal("0.0000")
    assert result.twenty_session_annualized_volatility_pct == Decimal("0.0000")


def test_global_decimal_context_does_not_change_metrics_or_regime() -> None:
    """调用线程的 Decimal 精度不得改变阈值附近的确定性事实。"""

    history = _historical_bars(
        [Decimal("100.1234567") + Decimal(index) / Decimal("7") for index in range(21)]
    )
    expected = calculate_market_regime(history)

    with localcontext() as context:
        context.prec = 6
        actual = calculate_market_regime(history)

    assert actual == expected


def test_direct_context_construction_rejects_regime_trigger_mismatch() -> None:
    """公开 Domain Fact 不允许 Regime 与原始指标 / Trigger 互相冲突。"""

    context = calculate_market_regime(_historical_bars([Decimal("100")] * 21))

    with pytest.raises(InvalidMarketContext, match="必须一致"):
        replace(
            context,
            regime=MarketRegime.HIGH_STRESS,
            triggered_rule_ids=("HIGH_VOLATILITY_GTE_40",),
        )


@pytest.mark.parametrize(
    ("ticker", "timeframe", "closes", "message"),
    [
        ("QQQ", "1Day", [Decimal("100")] * 21, "SPY"),
        ("SPY", "1Hour", [Decimal("100")] * 21, "1Day"),
        ("SPY", "1Day", [Decimal("100")] * 20, "21"),
    ],
)
def test_invalid_market_regime_inputs_have_stable_failures(
    ticker: str,
    timeframe: str,
    closes: list[Decimal],
    message: str,
) -> None:
    """市场代理、粒度和最低样本数是明确的领域边界。"""

    with pytest.raises(InvalidMarketContext, match=message):
        calculate_market_regime(_historical_bars(closes, ticker=ticker, timeframe=timeframe))
