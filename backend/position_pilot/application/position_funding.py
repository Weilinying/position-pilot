"""Position Plan 与当前 Ledger 仓位组合出的确定性资金快照。"""

from dataclasses import dataclass
from decimal import Decimal

from position_pilot.domain.portfolio import PortfolioState, PositionType


@dataclass(frozen=True, slots=True)
class PositionPlanIntent:
    """已确认的单个 Position Scope 目标资本配置。"""

    ticker: str
    position_type: PositionType
    target_budget: Decimal

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Position Plan ticker 不能为空")
        if self.position_type is PositionType.UNSPECIFIED:
            raise ValueError("Position Plan position_type 必须是 LONG_TERM 或 SWING")
        if self.target_budget <= 0:
            raise ValueError("Position Plan target_budget 必须大于 0")
        object.__setattr__(self, "ticker", normalized_ticker)


@dataclass(frozen=True, slots=True)
class PositionFundingSnapshot:
    """目标资本配置与当前仍持有仓位成本的确定性组合。"""

    ticker: str
    position_type: PositionType
    target_budget: Decimal
    open_quantity: Decimal
    average_cost: Decimal | None
    open_cost_basis: Decimal
    remaining_target_budget: Decimal

    @classmethod
    def from_portfolio(
        cls,
        portfolio: PortfolioState,
        intent: PositionPlanIntent,
    ) -> "PositionFundingSnapshot":
        """只使用当前 Position 成本基础计算剩余目标配置空间。"""

        position = next(
            (
                item
                for item in portfolio.positions
                if item.ticker == intent.ticker and item.position_type is intent.position_type
            ),
            None,
        )
        open_quantity = position.shares if position is not None else Decimal("0")
        open_cost_basis = position.cost_basis if position is not None else Decimal("0")
        remaining = max(intent.target_budget - open_cost_basis, Decimal("0"))
        return cls(
            ticker=intent.ticker,
            position_type=intent.position_type,
            target_budget=intent.target_budget,
            open_quantity=open_quantity,
            average_cost=position.average_cost if position is not None else None,
            open_cost_basis=open_cost_basis,
            remaining_target_budget=remaining,
        )

    def as_dict(self) -> dict[str, object]:
        """输出字段含义稳定的 LLM Context，不混入 Cash 或 Market Value。"""

        return {
            "ticker": self.ticker,
            "position_type": self.position_type.value,
            "target_budget": str(self.target_budget),
            "target_budget_semantics": "CURRENT_POSITION_CAPITAL_ALLOCATION",
            "open_quantity": str(self.open_quantity),
            "average_cost": (str(self.average_cost) if self.average_cost is not None else None),
            "open_cost_basis": str(self.open_cost_basis),
            "remaining_target_budget": str(self.remaining_target_budget),
            "remaining_target_budget_formula": ("max(target_budget - open_cost_basis, 0)"),
        }


def build_position_funding_snapshots(
    portfolio: PortfolioState,
    intents: tuple[PositionPlanIntent, ...],
) -> tuple[PositionFundingSnapshot, ...]:
    """为每个已确认 Intent 构造独立 Scope 快照。"""

    return tuple(
        PositionFundingSnapshot.from_portfolio(portfolio, intent)
        for intent in sorted(
            intents,
            key=lambda item: (item.ticker, item.position_type.value),
        )
    )
