"""AQ05 / AQ06 所需的最小金额分析与执行 UNKNOWN 边界。"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum


class PermissionStatus(StrEnum):
    """只表达本轮是否需要讨论账户权限。"""

    NOT_REQUESTED = "NOT_REQUESTED"
    USER_PROVIDED_CONDITION = "USER_PROVIDED_CONDITION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class InvestmentAnalysisFixture:
    """只包含金额分析、理论股数和预算边界所需事实。"""

    account_cash: Decimal
    current_turn_budget: Decimal
    quote: Decimal
    proposed_amounts: tuple[Decimal, ...] = ()
    share_count_requested: bool = False
    broker_permission_question: bool = False
    user_states_fractional_support: bool = False

    def __post_init__(self) -> None:
        if self.account_cash < 0 or self.current_turn_budget < 0 or self.quote <= 0:
            raise ValueError("Cash、Budget 不得为负，Quote 必须为正")
        if any(amount < 0 for amount in self.proposed_amounts):
            raise ValueError("资金分配金额不得为负")
        proposed_total = sum(self.proposed_amounts, start=Decimal("0"))
        if proposed_total > self.current_turn_budget:
            raise ValueError("资金分配不得超过用户本轮 Budget")


@dataclass(frozen=True, slots=True)
class InvestmentAnalysisBoundary:
    """允许金额分析，同时保持实际订单能力 UNKNOWN。"""

    account_cash: Decimal
    current_turn_budget: Decimal
    proposed_amounts: tuple[Decimal, ...]
    theoretical_share_quantity: Decimal | None
    executable_purchase_quantity: str
    permission_status: PermissionStatus
    fractional_research_required: bool


def investment_analysis_boundary(
    fixture: InvestmentAnalysisFixture,
) -> InvestmentAnalysisBoundary:
    """验证金额计划并在用户要求时计算非执行性的理论股数。"""

    theoretical_quantity = None
    if fixture.share_count_requested:
        theoretical_quantity = (fixture.current_turn_budget / fixture.quote).quantize(
            Decimal("0.0001"),
            rounding=ROUND_DOWN,
        )

    if fixture.user_states_fractional_support:
        permission_status = PermissionStatus.USER_PROVIDED_CONDITION
        research_required = False
    elif fixture.broker_permission_question:
        permission_status = PermissionStatus.UNKNOWN
        research_required = True
    else:
        permission_status = PermissionStatus.NOT_REQUESTED
        research_required = False

    return InvestmentAnalysisBoundary(
        account_cash=fixture.account_cash,
        current_turn_budget=fixture.current_turn_budget,
        proposed_amounts=fixture.proposed_amounts,
        theoretical_share_quantity=theoretical_quantity,
        executable_purchase_quantity="UNKNOWN",
        permission_status=permission_status,
        fractional_research_required=research_required,
    )
