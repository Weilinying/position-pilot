"""Investment Agent 注入 LLM 的 Structured Context 与确定性派生事实。"""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from uuid import UUID

from position_pilot.domain.market_data import HistoricalBars, MarketQuote
from position_pilot.domain.portfolio import PortfolioState, PositionType

WEIGHT_PERCENT_QUANTUM = Decimal("0.01")


class ContextCapabilityStatus(StrEnum):
    """某类 Context 数据来源当前是否可用。"""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ContextCapabilities:
    """与具体 Ticker Fact 分离的数据能力清单。"""

    current_quote: ContextCapabilityStatus = ContextCapabilityStatus.AVAILABLE
    price_history: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    news: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    earnings: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    fundamentals: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    market_context: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    technical_analysis: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    asset_metadata: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE
    sector_classification: ContextCapabilityStatus = ContextCapabilityStatus.UNAVAILABLE

    def as_dict(self) -> dict[str, str]:
        """生成发送给 LLM 的稳定 Capability Manifest。"""

        return {
            "current_quote": self.current_quote.value,
            "price_history": self.price_history.value,
            "news": self.news.value,
            "earnings": self.earnings.value,
            "fundamentals": self.fundamentals.value,
            "market_context": self.market_context.value,
            "technical_analysis": self.technical_analysis.value,
            "asset_metadata": self.asset_metadata.value,
            "sector_classification": self.sector_classification.value,
        }


class DecimalRelation(StrEnum):
    """由代码确定的两个 Decimal 之间的关系。"""

    ABOVE = "ABOVE"
    BELOW = "BELOW"
    EQUAL = "EQUAL"


class PriceDirection(StrEnum):
    """历史区间首尾收盘价的确定性方向。"""

    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"


M4_CONTEXT_CAPABILITIES = ContextCapabilities(
    price_history=ContextCapabilityStatus.AVAILABLE,
)


def m3_response_contract() -> dict[str, object]:
    """返回 M3 Final Response 必须遵守的结构化边界。"""

    return {
        "new_financial_calculations": "PROHIBITED",
        "unprovided_thresholds_or_rules": "PROHIBITED",
        "training_knowledge_as_missing_context": "PROHIBITED",
        "use_only_explicit_facts_and_relations": True,
    }


def m3_decision_context() -> dict[str, str]:
    """声明 M3 尚未获得的用户级持仓决策事实。"""

    return {
        "trading_plan": "UNKNOWN",
        "exit_conditions": "UNKNOWN",
        "risk_budget": "UNKNOWN",
    }


@dataclass(frozen=True, slots=True)
class PortfolioPositionSnapshot:
    """发送给 LLM 的单个当前 Position 事实。"""

    ticker: str
    position_type: PositionType
    shares: Decimal
    average_cost: Decimal
    cost_basis: Decimal

    def as_dict(self) -> dict[str, object]:
        """使用字符串保留 Decimal 精度。"""

        return {
            "ticker": self.ticker,
            "position_type": self.position_type.value,
            "shares": str(self.shares),
            "average_cost": str(self.average_cost),
            "cost_basis": str(self.cost_basis),
        }


@dataclass(frozen=True, slots=True)
class PortfolioDerivedFacts:
    """只包含当前 Eval 已证明需要的 Portfolio 确定性聚合事实。"""

    distinct_ticker_count: int
    total_position_cost_basis: Decimal
    total_shares_by_ticker: tuple[tuple[str, Decimal], ...]
    position_cost_basis_weight_by_ticker: tuple[tuple[str, Decimal], ...]

    @classmethod
    def from_positions(
        cls,
        positions: tuple[PortfolioPositionSnapshot, ...],
    ) -> "PortfolioDerivedFacts":
        """按 Ticker 聚合历史成本，分母明确排除 Available Cash。"""

        cost_basis_by_ticker: dict[str, Decimal] = {}
        shares_by_ticker: dict[str, Decimal] = {}
        for position in positions:
            cost_basis_by_ticker[position.ticker] = (
                cost_basis_by_ticker.get(position.ticker, Decimal("0")) + position.cost_basis
            )
            shares_by_ticker[position.ticker] = (
                shares_by_ticker.get(position.ticker, Decimal("0")) + position.shares
            )
        total_position_cost_basis = sum(
            cost_basis_by_ticker.values(),
            start=Decimal("0"),
        )
        weights = tuple(
            (
                ticker,
                (cost_basis / total_position_cost_basis * Decimal("100")).quantize(
                    WEIGHT_PERCENT_QUANTUM, rounding=ROUND_HALF_EVEN
                ),
            )
            for ticker, cost_basis in sorted(cost_basis_by_ticker.items())
        )
        return cls(
            distinct_ticker_count=len(cost_basis_by_ticker),
            total_position_cost_basis=total_position_cost_basis,
            total_shares_by_ticker=tuple(sorted(shares_by_ticker.items())),
            position_cost_basis_weight_by_ticker=weights,
        )

    def as_dict(self) -> dict[str, object]:
        """显式区分历史成本权重与当前市值权重。"""

        return {
            "distinct_ticker_count": self.distinct_ticker_count,
            "total_position_cost_basis": str(self.total_position_cost_basis),
            "total_shares_by_ticker": {
                ticker: str(shares) for ticker, shares in self.total_shares_by_ticker
            },
            "total_shares_by_ticker_scope": "same_ticker_aggregation_only",
            "position_cost_basis_weight_by_ticker": {
                ticker: f"{weight}%" for ticker, weight in self.position_cost_basis_weight_by_ticker
            },
            "position_cost_basis_weight_denominator": (
                "total_position_cost_basis_excluding_available_cash"
            ),
            "position_cost_basis_weight_unit": "PERCENT_ROUNDED_2DP",
            "current_market_value_weight": "UNAVAILABLE",
            "available_cash_weight": "UNAVAILABLE",
            "total_portfolio_value": "UNAVAILABLE",
            "portfolio_concentration_assessment": {
                "status": "UNKNOWN",
                "reason": "concentration_policy_and_user_risk_profile_unavailable",
            },
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """必定注入且不包含 Ledger History 的完整当前持仓快照。"""

    user_id: UUID
    available_cash: Decimal
    positions: tuple[PortfolioPositionSnapshot, ...]
    deterministic_derived_facts: PortfolioDerivedFacts
    positions_are_complete: bool = True

    @classmethod
    def from_state(cls, state: PortfolioState) -> "PortfolioSnapshot":
        """从确定性 Portfolio State 创建稳定 Snapshot。"""

        positions = tuple(
            PortfolioPositionSnapshot(
                ticker=position.ticker,
                position_type=position.position_type,
                shares=position.shares,
                average_cost=position.average_cost,
                cost_basis=position.cost_basis,
            )
            for position in sorted(
                state.positions,
                key=lambda item: (item.ticker, item.position_type.value),
            )
        )
        return cls(
            user_id=state.user_id,
            available_cash=state.cash.available_cash,
            positions=positions,
            deterministic_derived_facts=PortfolioDerivedFacts.from_positions(positions),
        )

    def as_dict(self) -> dict[str, object]:
        """显式声明 Positions 完整及缺席 Ticker 的含义。"""

        return {
            "available_cash": str(self.available_cash),
            "positions_are_complete_current_set": self.positions_are_complete,
            "missing_ticker_means_no_current_position": True,
            "positions": [position.as_dict() for position in self.positions],
            "deterministic_derived_facts": self.deterministic_derived_facts.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class PositionPriceRelation:
    """Current Quote 与某个保留 Position Type 的 Average Cost 关系。"""

    ticker: str
    position_type: PositionType
    price_vs_average_cost: DecimalRelation

    def as_dict(self) -> dict[str, str]:
        """保留 Position Type 输出代码计算的价格关系。"""

        return {
            "ticker": self.ticker,
            "position_type": self.position_type.value,
            "price_vs_average_cost": self.price_vs_average_cost.value,
        }


@dataclass(frozen=True, slots=True)
class QuoteDerivedFacts:
    """Quote 成功后自动产生的最小确定性关系，不表示交易可执行性。"""

    cash_vs_one_share_price: DecimalRelation
    price_vs_average_cost_by_position: tuple[PositionPriceRelation, ...]
    executable_purchase_quantity: str = "UNKNOWN"

    @classmethod
    def from_quote(
        cls,
        snapshot: PortfolioSnapshot,
        quote: MarketQuote,
    ) -> "QuoteDerivedFacts":
        """只为 Quote 对应的现有 Position 生成成本关系。"""

        relations = tuple(
            PositionPriceRelation(
                ticker=position.ticker,
                position_type=position.position_type,
                price_vs_average_cost=_decimal_relation(
                    quote.last_price,
                    position.average_cost,
                ),
            )
            for position in snapshot.positions
            if position.ticker == quote.ticker
        )
        return cls(
            cash_vs_one_share_price=_decimal_relation(
                snapshot.available_cash,
                quote.last_price,
            ),
            price_vs_average_cost_by_position=relations,
        )

    def as_dict(self) -> dict[str, object]:
        """输出不包含购买股数或 Position Sizing 的派生事实。"""

        return {
            "cash_vs_one_share_price": {
                "relation": self.cash_vs_one_share_price.value,
                "meaning": "numeric_comparison_only",
                "supports_purchase_execution_conclusion": False,
                "prohibited_interpretations": [
                    "cash_is_sufficient_or_insufficient_to_buy",
                    "can_or_cannot_buy_one_share",
                    "cash_covers_or_does_not_cover_one_share",
                ],
            },
            "executable_purchase_quantity": {
                "status": self.executable_purchase_quantity,
                "reason": "asset_metadata_and_order_capabilities_unavailable",
            },
            "price_vs_average_cost_by_position": [
                relation.as_dict() for relation in self.price_vs_average_cost_by_position
            ],
        }


def quote_response_contract() -> dict[str, object]:
    """在最接近 Final Completion 的 Tool Result 中重申可验证边界。"""

    return {
        "cross_ticker_quote_comparison": "PROHIBITED_UNLESS_PROVIDED",
        "new_financial_calculations": "PROHIBITED",
        "purchase_execution_conclusion": "PROHIBITED",
        "cash_quote_relation_allowed_use": "repeat_relation_only",
        "required_purchase_execution_status": "UNKNOWN",
    }


@dataclass(frozen=True, slots=True)
class RecentPriceHistoryFacts:
    """从固定 Daily Bars 窗口确定性派生的近期价格事实。"""

    ticker: str
    bar_count: int
    period_start: str
    period_end: str
    first_close: Decimal
    latest_close: Decimal
    period_high: Decimal
    period_low: Decimal
    close_change: Decimal
    absolute_close_change: Decimal
    close_change_percent: Decimal
    absolute_close_change_percent: Decimal
    close_direction: PriceDirection

    @classmethod
    def from_historical_bars(cls, historical_bars: HistoricalBars) -> "RecentPriceHistoryFacts":
        """只计算区间描述事实，不产生技术信号或预测。"""

        bars = historical_bars.bars
        first_close = bars[0].close
        latest_close = bars[-1].close
        close_change = latest_close - first_close
        close_change_percent = (close_change / first_close * Decimal("100")).quantize(
            WEIGHT_PERCENT_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
        direction = PriceDirection.FLAT
        if close_change > 0:
            direction = PriceDirection.UP
        elif close_change < 0:
            direction = PriceDirection.DOWN
        return cls(
            ticker=historical_bars.ticker,
            bar_count=len(bars),
            period_start=bars[0].timestamp.isoformat(),
            period_end=bars[-1].timestamp.isoformat(),
            first_close=first_close,
            latest_close=latest_close,
            period_high=max(bar.high for bar in bars),
            period_low=min(bar.low for bar in bars),
            close_change=close_change,
            absolute_close_change=abs(close_change),
            close_change_percent=close_change_percent,
            absolute_close_change_percent=abs(close_change_percent),
            close_direction=direction,
        )

    def as_dict(self) -> dict[str, object]:
        """使用字符串保留 Decimal，并明确事实不等于技术分析。"""

        return {
            "ticker": self.ticker,
            "bar_count": self.bar_count,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "first_close": str(self.first_close),
            "latest_close": str(self.latest_close),
            "period_high": str(self.period_high),
            "period_low": str(self.period_low),
            "close_change": str(self.close_change),
            "absolute_close_change": str(self.absolute_close_change),
            "close_change_percent": f"{self.close_change_percent}%",
            "absolute_close_change_percent": f"{self.absolute_close_change_percent}%",
            "close_direction": self.close_direction.value,
            "interpretation_scope": "observed_adjusted_daily_price_path_only",
            "technical_signal": "UNAVAILABLE",
            "prediction": "UNAVAILABLE",
        }


def recent_price_history_response_contract() -> dict[str, object]:
    """限制历史价格事实的解释范围。"""

    return {
        "use_only_provided_history_facts": True,
        "latest_historical_close_is_current_quote": False,
        "technical_analysis": "UNAVAILABLE",
        "support_resistance": "UNAVAILABLE",
        "moving_average": "UNAVAILABLE",
        "rsi": "UNAVAILABLE",
        "prediction": "PROHIBITED",
        "buy_sell_signal": "PROHIBITED",
    }


def _decimal_relation(left: Decimal, right: Decimal) -> DecimalRelation:
    """只比较数值关系，不让 LLM 从原始数字自行派生。"""

    if left > right:
        return DecimalRelation.ABOVE
    if left < right:
        return DecimalRelation.BELOW
    return DecimalRelation.EQUAL
