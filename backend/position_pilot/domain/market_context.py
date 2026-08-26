"""整体市场 Context 的确定性 Regime 计算。"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum

from position_pilot.domain.market_data import HistoricalBars, MarketDataCoverage

MARKET_PROXY_TICKER = "SPY"
DAILY_TIMEFRAME = "1Day"
MINIMUM_OBSERVATION_COUNT = 21
REGIME_METHODOLOGY = "V1_HEURISTIC"
REGIME_VERSION = "1.0"
REGIME_DISCLAIMER = (
    "这些 Market Regime 阈值属于 V1 工程启发式规则，并非行业标准、未经历史回测验证，"
    "且不构成投资信号。"
)
_QUANTUM = Decimal("0.0001")
_ANNUALIZATION_FACTOR = Decimal(252)
_ELEVATED_VOLATILITY = Decimal(25)
_ELEVATED_DRAWDOWN = Decimal(-5)
_ELEVATED_RETURN_5D = Decimal(-3)
_HIGH_VOLATILITY = Decimal(40)
_HIGH_DRAWDOWN = Decimal(-10)
_HIGH_RETURN_5D = Decimal(-6)
_EXTREME_VOLATILITY = Decimal(60)
_EXTREME_DRAWDOWN = Decimal(-15)
_EXTREME_RETURN_5D = Decimal(-10)


class InvalidMarketContext(ValueError):
    """Market Context 输入不满足已批准的确定性计算边界。"""


class MarketRegime(StrEnum):
    """V1 可解释的整体市场压力等级。"""

    NORMAL = "NORMAL"
    ELEVATED_VOLATILITY = "ELEVATED_VOLATILITY"
    HIGH_STRESS = "HIGH_STRESS"
    EXTREME_STRESS = "EXTREME_STRESS"


@dataclass(frozen=True, slots=True)
class MarketRegimeContext:
    """保留计算指标和 Provider 元数据的整体市场 Context。"""

    regime: MarketRegime
    five_session_return_pct: Decimal
    twenty_session_drawdown_pct: Decimal
    twenty_session_annualized_volatility_pct: Decimal
    triggered_rule_ids: tuple[str, ...]
    period_start: datetime
    period_end: datetime
    observation_count: int
    source: str
    feed: str
    coverage: MarketDataCoverage
    currency: str
    adjustment: str
    fetched_at: datetime
    methodology: str = REGIME_METHODOLOGY
    version: str = REGIME_VERSION
    disclaimer: str = REGIME_DISCLAIMER

    def __post_init__(self) -> None:
        if not isinstance(self.regime, MarketRegime):
            raise InvalidMarketContext("regime 无效")
        for field_name in (
            "five_session_return_pct",
            "twenty_session_drawdown_pct",
            "twenty_session_annualized_volatility_pct",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise InvalidMarketContext(f"{field_name} 必须是有限 Decimal")
            if value != value.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN):
                raise InvalidMarketContext(f"{field_name} 必须保留四位小数")
        if not isinstance(self.triggered_rule_ids, tuple) or any(
            not isinstance(rule_id, str) or not rule_id for rule_id in self.triggered_rule_ids
        ):
            raise InvalidMarketContext("triggered_rule_ids 必须是非空字符串 tuple")
        if self.observation_count < MINIMUM_OBSERVATION_COUNT:
            raise InvalidMarketContext("observation_count 不得少于 21")
        if self.period_start > self.period_end:
            raise InvalidMarketContext("period_start 不得晚于 period_end")
        if self.twenty_session_drawdown_pct > 0:
            raise InvalidMarketContext("twenty_session_drawdown_pct 不得大于零")
        if self.twenty_session_annualized_volatility_pct < 0:
            raise InvalidMarketContext("twenty_session_annualized_volatility_pct 不得小于零")
        expected_regime, expected_rule_ids = classify_market_regime(
            five_session_return_pct=self.five_session_return_pct,
            twenty_session_drawdown_pct=self.twenty_session_drawdown_pct,
            twenty_session_annualized_volatility_pct=(
                self.twenty_session_annualized_volatility_pct
            ),
        )
        if self.regime is not expected_regime or self.triggered_rule_ids != expected_rule_ids:
            raise InvalidMarketContext("regime、指标与 triggered_rule_ids 必须一致")
        if self.methodology != REGIME_METHODOLOGY:
            raise InvalidMarketContext("methodology 必须为 V1_HEURISTIC")
        if self.version != REGIME_VERSION:
            raise InvalidMarketContext("version 必须为 1.0")
        if self.disclaimer != REGIME_DISCLAIMER:
            raise InvalidMarketContext("disclaimer 必须使用已批准声明")


def calculate_market_regime(historical_bars: HistoricalBars) -> MarketRegimeContext:
    """基于最近 21 根已完成 SPY 日线计算 V1 Market Regime。

    输入价格和输出指标均由确定性代码处理；本规则仅描述市场压力，不能推导买卖结论。
    """

    if historical_bars.ticker != MARKET_PROXY_TICKER:
        raise InvalidMarketContext("Market Regime 仅支持 SPY 市场代理")
    if historical_bars.timeframe != DAILY_TIMEFRAME:
        raise InvalidMarketContext("Market Regime 仅支持 1Day completed Daily Bars")
    if len(historical_bars.bars) < MINIMUM_OBSERVATION_COUNT:
        raise InvalidMarketContext("Market Regime 至少需要 21 根 completed Daily Bars")

    bars = historical_bars.bars[-MINIMUM_OBSERVATION_COUNT:]
    closes = tuple(bar.close for bar in bars)
    with localcontext() as context:
        context.prec = 50
        five_session_return_pct = _percent_change(closes[-6], closes[-1])
        twenty_session_drawdown_pct = _percent_change(max(closes[-20:]), closes[-1])
        daily_returns = tuple(
            _percent_change(previous_close, close) / Decimal(100)
            for previous_close, close in zip(closes[:-1], closes[1:], strict=True)
        )
        volatility_pct = _annualized_volatility_pct(daily_returns)
        quantized_five_session_return = _quantize(five_session_return_pct)
        quantized_drawdown = _quantize(twenty_session_drawdown_pct)
        quantized_volatility = _quantize(volatility_pct)
    regime, triggered_rule_ids = classify_market_regime(
        five_session_return_pct=quantized_five_session_return,
        twenty_session_drawdown_pct=quantized_drawdown,
        twenty_session_annualized_volatility_pct=quantized_volatility,
    )

    return MarketRegimeContext(
        regime=regime,
        five_session_return_pct=quantized_five_session_return,
        twenty_session_drawdown_pct=quantized_drawdown,
        twenty_session_annualized_volatility_pct=quantized_volatility,
        triggered_rule_ids=triggered_rule_ids,
        period_start=bars[0].timestamp,
        period_end=bars[-1].timestamp,
        observation_count=len(bars),
        source=historical_bars.source,
        feed=historical_bars.feed,
        coverage=historical_bars.coverage,
        currency=historical_bars.currency,
        adjustment=historical_bars.adjustment,
        fetched_at=historical_bars.fetched_at,
    )


def _percent_change(base: Decimal, current: Decimal) -> Decimal:
    """返回相对基准价格的百分比变化。"""

    with localcontext() as context:
        context.prec = 50
        return (current / base - Decimal(1)) * Decimal(100)


def _sample_standard_deviation(values: tuple[Decimal, ...]) -> Decimal:
    """使用 sample standard deviation，避免退化为总体波动率。"""

    if len(values) < 2:
        raise InvalidMarketContext("波动率至少需要两个日收益率")
    with localcontext() as context:
        context.prec = 50
        mean = sum(values, start=Decimal(0)) / Decimal(len(values))
        variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values) - 1)
        return variance.sqrt()


def _annualized_volatility_pct(daily_returns: tuple[Decimal, ...]) -> Decimal:
    """在固定高精度 Decimal 上下文中年化日收益率样本波动率。"""

    with localcontext() as context:
        context.prec = 50
        return (
            _sample_standard_deviation(daily_returns) * _ANNUALIZATION_FACTOR.sqrt() * Decimal(100)
        )


def _quantize(value: Decimal) -> Decimal:
    """统一使用 half-even 保留四位小数，确保阈值判定可复现。"""

    with localcontext() as context:
        context.prec = 50
        return value.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)


def classify_market_regime(
    *,
    five_session_return_pct: Decimal,
    twenty_session_drawdown_pct: Decimal,
    twenty_session_annualized_volatility_pct: Decimal,
) -> tuple[MarketRegime, tuple[str, ...]]:
    """按已量化的指标返回最高严重度及其实际命中的规则。"""

    rules_by_severity = (
        (
            MarketRegime.EXTREME_STRESS,
            (
                (
                    "EXTREME_VOLATILITY_GTE_60",
                    twenty_session_annualized_volatility_pct >= _EXTREME_VOLATILITY,
                ),
                (
                    "EXTREME_DRAWDOWN_LTE_NEGATIVE_15",
                    twenty_session_drawdown_pct <= _EXTREME_DRAWDOWN,
                ),
                (
                    "EXTREME_RETURN_5D_LTE_NEGATIVE_10",
                    five_session_return_pct <= _EXTREME_RETURN_5D,
                ),
            ),
        ),
        (
            MarketRegime.HIGH_STRESS,
            (
                (
                    "HIGH_VOLATILITY_GTE_40",
                    twenty_session_annualized_volatility_pct >= _HIGH_VOLATILITY,
                ),
                (
                    "HIGH_DRAWDOWN_LTE_NEGATIVE_10",
                    twenty_session_drawdown_pct <= _HIGH_DRAWDOWN,
                ),
                (
                    "HIGH_RETURN_5D_LTE_NEGATIVE_6",
                    five_session_return_pct <= _HIGH_RETURN_5D,
                ),
            ),
        ),
        (
            MarketRegime.ELEVATED_VOLATILITY,
            (
                (
                    "ELEVATED_VOLATILITY_GTE_25",
                    twenty_session_annualized_volatility_pct >= _ELEVATED_VOLATILITY,
                ),
                (
                    "ELEVATED_DRAWDOWN_LTE_NEGATIVE_5",
                    twenty_session_drawdown_pct <= _ELEVATED_DRAWDOWN,
                ),
                (
                    "ELEVATED_RETURN_5D_LTE_NEGATIVE_3",
                    five_session_return_pct <= _ELEVATED_RETURN_5D,
                ),
            ),
        ),
    )
    for regime, rules in rules_by_severity:
        triggered_rule_ids = tuple(rule_id for rule_id, is_triggered in rules if is_triggered)
        if triggered_rule_ids:
            return regime, triggered_rule_ids
    return MarketRegime.NORMAL, ()


def market_regime_thresholds_as_dict() -> dict[str, dict[str, str]]:
    """暴露实际参与分类的阈值，便于 Tool Trace、Eval 与未来 Backtest。"""

    return {
        MarketRegime.ELEVATED_VOLATILITY.value: {
            "annualized_realized_volatility_percent_gte": str(_ELEVATED_VOLATILITY),
            "close_drawdown_percent_lte": str(_ELEVATED_DRAWDOWN),
            "five_session_return_percent_lte": str(_ELEVATED_RETURN_5D),
        },
        MarketRegime.HIGH_STRESS.value: {
            "annualized_realized_volatility_percent_gte": str(_HIGH_VOLATILITY),
            "close_drawdown_percent_lte": str(_HIGH_DRAWDOWN),
            "five_session_return_percent_lte": str(_HIGH_RETURN_5D),
        },
        MarketRegime.EXTREME_STRESS.value: {
            "annualized_realized_volatility_percent_gte": str(_EXTREME_VOLATILITY),
            "close_drawdown_percent_lte": str(_EXTREME_DRAWDOWN),
            "five_session_return_percent_lte": str(_EXTREME_RETURN_5D),
        },
    }
