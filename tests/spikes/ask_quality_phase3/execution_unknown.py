"""AQ05 / AQ06 所需的最小 Execution UNKNOWN 边界。"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class FactState(StrEnum):
    """Phase 3 只区分已确认与 UNKNOWN，不定义完整执行 Contract。"""

    VERIFIED_TRUE = "VERIFIED_TRUE"
    VERIFIED_FALSE = "VERIFIED_FALSE"
    UNKNOWN = "UNKNOWN"


class Authority(StrEnum):
    """来源能否确认公开规则或当前 Account 权限。"""

    PUBLIC = "PUBLIC"
    ACCOUNT_AUTHENTICATED = "ACCOUNT_AUTHENTICATED"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class ExecutionUnknownFixture:
    """只包含 AQ05 / AQ06 的必要事实。"""

    account_cash: Decimal
    current_turn_budget: Decimal
    quote: Decimal
    ticker_fractional_rule: FactState = FactState.UNKNOWN
    account_permission: FactState = FactState.UNKNOWN

    def __post_init__(self) -> None:
        if any(value < 0 for value in (self.account_cash, self.current_turn_budget, self.quote)):
            raise ValueError("Cash、Budget 与 Quote 不得为负")


@dataclass(frozen=True, slots=True)
class ExecutionBoundaryResult:
    """供回答使用的条件结论，不是 Broker Execution Contract。"""

    account_cash: Decimal
    current_turn_budget: Decimal
    quote: Decimal
    whole_share_budget_condition: str
    fractional_condition: str
    account_permission: FactState


def execution_boundary(fixture: ExecutionUnknownFixture) -> ExecutionBoundaryResult:
    """预算只影响本轮分析，不覆盖 Cash，也不把未知权限补成事实。"""

    if fixture.current_turn_budget < fixture.quote:
        whole_share_condition = "BUDGET_BELOW_ONE_SHARE_QUOTE"
    else:
        whole_share_condition = "BUDGET_AT_OR_ABOVE_ONE_SHARE_QUOTE"
    if fixture.ticker_fractional_rule is FactState.VERIFIED_FALSE:
        fractional_condition = "FRACTIONAL_NOT_SUPPORTED"
    elif (
        fixture.ticker_fractional_rule is FactState.VERIFIED_TRUE
        and fixture.account_permission is FactState.VERIFIED_TRUE
    ):
        fractional_condition = "FRACTIONAL_CONDITION_CONFIRMED"
    else:
        fractional_condition = "FRACTIONAL_EXECUTION_UNKNOWN"
    return ExecutionBoundaryResult(
        fixture.account_cash,
        fixture.current_turn_budget,
        fixture.quote,
        whole_share_condition,
        fractional_condition,
        fixture.account_permission,
    )


def apply_execution_evidence(
    *,
    observed_state: FactState,
    authority: Authority,
) -> tuple[FactState, FactState]:
    """公开来源只能确认公开规则，不能确认当前 Account 权限。"""

    if authority is Authority.NONE:
        return FactState.UNKNOWN, FactState.UNKNOWN
    if authority is Authority.PUBLIC:
        return observed_state, FactState.UNKNOWN
    return FactState.UNKNOWN, observed_state
