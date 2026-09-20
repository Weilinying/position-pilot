"""AQ05 / AQ06 UNKNOWN 与来源权威测试。"""

from dataclasses import fields
from decimal import Decimal

import pytest

from .execution_unknown import (
    Authority,
    ExecutionBoundaryResult,
    ExecutionUnknownFixture,
    FactState,
    apply_execution_evidence,
    execution_boundary,
)


def test_execution_boundary_does_not_invent_quantity_or_budget_advice() -> None:
    """Prototype 只表达条件，不输出确定数量或提高预算建议。"""

    assert {field.name for field in fields(ExecutionBoundaryResult)} == {
        "account_cash",
        "current_turn_budget",
        "quote",
        "whole_share_budget_condition",
        "fractional_condition",
        "account_permission",
    }


@pytest.mark.parametrize(
    ("budget", "expected_condition"),
    [
        (Decimal("500"), "BUDGET_AT_OR_ABOVE_ONE_SHARE_QUOTE"),
        (Decimal("200"), "BUDGET_BELOW_ONE_SHARE_QUOTE"),
    ],
)
def test_aq05_aq06_budget_changes_condition_without_overwriting_cash(
    budget: Decimal,
    expected_condition: str,
) -> None:
    """受控对照只改变本轮 Budget，Ledger Cash 保持不变。"""

    result = execution_boundary(
        ExecutionUnknownFixture(
            account_cash=Decimal("4875.77"),
            current_turn_budget=budget,
            quote=Decimal("210.25"),
        )
    )

    assert result.account_cash == Decimal("4875.77")
    assert result.current_turn_budget == budget
    assert result.quote == Decimal("210.25")
    assert result.whole_share_budget_condition == expected_condition
    assert result.fractional_condition == "FRACTIONAL_EXECUTION_UNKNOWN"
    assert result.account_permission is FactState.UNKNOWN


def test_public_fractional_rule_cannot_confirm_account_permission() -> None:
    """公开 Broker / Ticker 规则不能冒充当前 Account 权限。"""

    ticker_rule, account_permission = apply_execution_evidence(
        observed_state=FactState.VERIFIED_TRUE,
        authority=Authority.PUBLIC,
    )
    result = execution_boundary(
        ExecutionUnknownFixture(
            Decimal("4875.77"),
            Decimal("200"),
            Decimal("210.25"),
            ticker_rule,
            account_permission,
        )
    )

    assert ticker_rule is FactState.VERIFIED_TRUE
    assert account_permission is FactState.UNKNOWN
    assert result.fractional_condition == "FRACTIONAL_EXECUTION_UNKNOWN"


@pytest.mark.parametrize("authority", [Authority.PUBLIC, Authority.ACCOUNT_AUTHENTICATED])
def test_no_result_or_provider_failure_keeps_execution_fact_unknown(
    authority: Authority,
) -> None:
    """没有观察到规则时不得把 Failure / No Result 改写成已确认能力。"""

    ticker_rule, account_permission = apply_execution_evidence(
        observed_state=FactState.UNKNOWN,
        authority=authority,
    )

    assert ticker_rule is FactState.UNKNOWN
    assert account_permission is FactState.UNKNOWN


def test_fractional_condition_requires_both_rule_and_account_authority() -> None:
    """只有公开规则与 Account 权限分别确认后才允许确认碎股条件。"""

    public_rule, _ = apply_execution_evidence(
        observed_state=FactState.VERIFIED_TRUE,
        authority=Authority.PUBLIC,
    )
    _, account_permission = apply_execution_evidence(
        observed_state=FactState.VERIFIED_TRUE,
        authority=Authority.ACCOUNT_AUTHENTICATED,
    )

    result = execution_boundary(
        ExecutionUnknownFixture(
            Decimal("4875.77"),
            Decimal("200"),
            Decimal("210.25"),
            public_rule,
            account_permission,
        )
    )

    assert result.fractional_condition == "FRACTIONAL_CONDITION_CONFIRMED"
