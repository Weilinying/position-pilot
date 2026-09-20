"""AQ05 / AQ06 金额分析、预算与执行 UNKNOWN 测试。"""

from decimal import Decimal

import pytest

from .execution_unknown import (
    InvestmentAnalysisFixture,
    PermissionStatus,
    investment_analysis_boundary,
)


def test_aq06_allows_amount_plan_without_fractional_permission_lookup() -> None:
    """普通金额分配不以碎股权限为前置条件。"""

    result = investment_analysis_boundary(
        InvestmentAnalysisFixture(
            account_cash=Decimal("4875.77"),
            current_turn_budget=Decimal("200"),
            quote=Decimal("210.25"),
            proposed_amounts=(Decimal("80"), Decimal("120")),
        )
    )

    assert result.account_cash == Decimal("4875.77")
    assert result.current_turn_budget == Decimal("200")
    assert result.proposed_amounts == (Decimal("80"), Decimal("120"))
    assert result.permission_status is PermissionStatus.NOT_REQUESTED
    assert result.fractional_research_required is False
    assert result.executable_purchase_quantity == "UNKNOWN"


def test_amount_plan_has_no_hard_coded_allocation_ratio() -> None:
    """不同的预算内金额方案都可通过，不冻结示例比例。"""

    for amounts in ((Decimal("50"), Decimal("150")), (Decimal("200"),)):
        result = investment_analysis_boundary(
            InvestmentAnalysisFixture(
                Decimal("4875.77"), Decimal("200"), Decimal("210.25"), amounts
            )
        )
        assert sum(result.proposed_amounts, start=Decimal("0")) == Decimal("200")


def test_user_stated_fractional_support_is_accepted_without_reverification() -> None:
    """用户明确提供的碎股条件可直接用于本轮分析。"""

    result = investment_analysis_boundary(
        InvestmentAnalysisFixture(
            Decimal("4875.77"),
            Decimal("200"),
            Decimal("210.25"),
            user_states_fractional_support=True,
        )
    )

    assert result.permission_status is PermissionStatus.USER_PROVIDED_CONDITION
    assert result.fractional_research_required is False


def test_requested_share_count_is_theoretical_not_executable() -> None:
    """理论股数由预算和可靠价格计算，但不升级为订单数量。"""

    result = investment_analysis_boundary(
        InvestmentAnalysisFixture(
            Decimal("4875.77"),
            Decimal("200"),
            Decimal("210.25"),
            share_count_requested=True,
        )
    )

    assert result.theoretical_share_quantity == Decimal("0.9512")
    assert result.executable_purchase_quantity == "UNKNOWN"


def test_only_explicit_permission_question_requests_permission_research() -> None:
    """只有明确的券商权限问题才保留 UNKNOWN 并触发查证需求。"""

    result = investment_analysis_boundary(
        InvestmentAnalysisFixture(
            Decimal("4875.77"),
            Decimal("200"),
            Decimal("210.25"),
            broker_permission_question=True,
        )
    )

    assert result.permission_status is PermissionStatus.UNKNOWN
    assert result.fractional_research_required is True


def test_budget_above_ledger_cash_remains_separate_analysis_context() -> None:
    """本轮 Budget 不覆盖 Ledger Cash，也不自动成为可执行资金。"""

    result = investment_analysis_boundary(
        InvestmentAnalysisFixture(
            Decimal("100"),
            Decimal("200"),
            Decimal("210.25"),
            proposed_amounts=(Decimal("200"),),
        )
    )

    assert result.account_cash == Decimal("100")
    assert result.current_turn_budget == Decimal("200")
    assert result.executable_purchase_quantity == "UNKNOWN"


@pytest.mark.parametrize(
    "amounts",
    [(Decimal("201"),), (Decimal("100"), Decimal("101"))],
)
def test_amount_plan_cannot_exceed_current_turn_budget(
    amounts: tuple[Decimal, ...],
) -> None:
    """建议不得擅自提高用户本轮 Budget。"""

    with pytest.raises(ValueError, match="本轮 Budget"):
        InvestmentAnalysisFixture(Decimal("4875.77"), Decimal("200"), Decimal("210.25"), amounts)
