"""Portfolio 领域计算测试。"""

from datetime import UTC, datetime
from decimal import Decimal
from inspect import signature
from typing import cast
from uuid import UUID

import pytest

from position_pilot.domain.errors import (
    InsufficientCash,
    InsufficientShares,
    InvalidLedger,
    InvalidPortfolioValue,
)
from position_pilot.domain.portfolio import (
    PositionType,
    Transaction,
    TransactionAction,
    User,
    calculate_amount,
    rebuild_portfolio,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OCCURRED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def make_user(initial_cash: str = "1000") -> User:
    """创建固定标识的测试 User。"""

    return User.create(
        user_id=USER_ID,
        display_name="测试用户",
        initial_cash=Decimal(initial_cash),
        created_at=OCCURRED_AT,
    )


def make_transaction(
    *,
    sequence: int,
    action: TransactionAction,
    price: str,
    shares: str,
    position_type: PositionType = PositionType.LONG_TERM,
    ticker: str = "GOOG",
) -> Transaction:
    """创建确定时间的测试 Transaction。"""

    return Transaction.create(
        user_id=USER_ID,
        sequence=sequence,
        ticker=ticker,
        action=action,
        price=Decimal(price),
        shares=Decimal(shares),
        position_type=position_type,
        occurred_at=OCCURRED_AT,
    )


def test_transaction_amount_is_derived_and_not_a_create_input() -> None:
    """amount 应只读派生，不能出现在 Transaction 写入参数中。"""

    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="220.5",
        shares="0.45",
    )

    assert transaction.amount == Decimal("99.22500000")
    assert "amount" not in signature(Transaction.create).parameters
    assert calculate_amount(Decimal("220.5"), Decimal("0.45")) == Decimal("99.22500000")


def test_rebuilds_weighted_average_cost_and_cash() -> None:
    """多次 BUY 应确定性计算 Shares、Cost Basis、Average Cost 与 Cash。"""

    state = rebuild_portfolio(
        make_user(),
        [
            make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="10"),
            make_transaction(sequence=2, action=TransactionAction.BUY, price="20", shares="20"),
        ],
    )

    position = state.get_position("goog", PositionType.LONG_TERM)
    assert position is not None
    assert position.shares == Decimal("30.00000000")
    assert position.cost_basis == Decimal("500.00000000")
    assert position.average_cost == Decimal("16.66666667")
    assert state.cash.available_cash == Decimal("500.00000000")
    assert state.transaction_count == 2


def test_long_term_and_swing_are_independent_for_same_ticker() -> None:
    """同一 Ticker 的两类仓位不得相互合并或互相提供 Shares。"""

    state = rebuild_portfolio(
        make_user(),
        [
            make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="5"),
            make_transaction(
                sequence=2,
                action=TransactionAction.BUY,
                price="20",
                shares="2",
                position_type=PositionType.SWING,
            ),
        ],
    )

    long_term = state.get_position("GOOG", PositionType.LONG_TERM)
    swing = state.get_position("GOOG", PositionType.SWING)
    assert long_term is not None and long_term.shares == Decimal("5.00000000")
    assert swing is not None and swing.shares == Decimal("2.00000000")
    assert len(state.positions) == 2


def test_partial_sell_preserves_average_cost_and_updates_cash() -> None:
    """部分 SELL 只减少 Shares 与 Cost Basis，不改变剩余 Average Cost。"""

    state = rebuild_portfolio(
        make_user(),
        [
            make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="10"),
            make_transaction(sequence=2, action=TransactionAction.SELL, price="15", shares="4"),
        ],
    )

    position = state.get_position("GOOG", PositionType.LONG_TERM)
    assert position is not None
    assert position.shares == Decimal("6.00000000")
    assert position.cost_basis == Decimal("60.00000000")
    assert position.average_cost == Decimal("10.00000000")
    assert state.cash.available_cash == Decimal("960.00000000")


def test_full_sell_removes_only_matching_position() -> None:
    """全部 SELL 应移除目标仓位，但保留同 Ticker 的另一 Position Type。"""

    state = rebuild_portfolio(
        make_user(),
        [
            make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="5"),
            make_transaction(
                sequence=2,
                action=TransactionAction.BUY,
                price="10",
                shares="3",
                position_type=PositionType.SWING,
            ),
            make_transaction(sequence=3, action=TransactionAction.SELL, price="12", shares="5"),
        ],
    )

    assert state.get_position("GOOG", PositionType.LONG_TERM) is None
    assert state.get_position("GOOG", PositionType.SWING) is not None


def test_buy_rejects_insufficient_cash() -> None:
    """BUY 不得令 Available Cash 变为负数。"""

    with pytest.raises(InsufficientCash) as error:
        rebuild_portfolio(
            make_user("100"),
            [make_transaction(sequence=1, action=TransactionAction.BUY, price="20", shares="6")],
        )

    assert error.value.available == Decimal("100.00000000")
    assert error.value.required == Decimal("120.00000000")


def test_sell_rejects_oversell_for_matching_position_type() -> None:
    """SELL 只能使用同 Position Type 的可用 Shares。"""

    with pytest.raises(InsufficientShares) as error:
        rebuild_portfolio(
            make_user(),
            [
                make_transaction(
                    sequence=1,
                    action=TransactionAction.BUY,
                    price="10",
                    shares="5",
                    position_type=PositionType.SWING,
                ),
                make_transaction(
                    sequence=2,
                    action=TransactionAction.SELL,
                    price="12",
                    shares="1",
                    position_type=PositionType.LONG_TERM,
                ),
            ],
        )

    assert error.value.available == Decimal("0")


def test_rejects_more_than_eight_decimal_places() -> None:
    """持久化金融输入不得超过批准的 8 位小数精度。"""

    with pytest.raises(InvalidPortfolioValue, match="8 位小数"):
        make_transaction(
            sequence=1,
            action=TransactionAction.BUY,
            price="1.000000001",
            shares="1",
        )


@pytest.mark.parametrize(
    ("action", "position_type", "expected_message"),
    [
        (cast(TransactionAction, "DIVIDEND"), PositionType.LONG_TERM, "action"),
        (TransactionAction.BUY, cast(PositionType, "DAY_TRADE"), "position_type"),
    ],
)
def test_rejects_unknown_transaction_enums(
    action: TransactionAction,
    position_type: PositionType,
    expected_message: str,
) -> None:
    """未知枚举不得静默进入 BUY / SELL 或 Position 计算分支。"""

    with pytest.raises(InvalidPortfolioValue, match=expected_message):
        Transaction.create(
            user_id=USER_ID,
            sequence=1,
            ticker="GOOG",
            action=action,
            price=Decimal("10"),
            shares=Decimal("1"),
            position_type=position_type,
            occurred_at=OCCURRED_AT,
        )


def test_rejects_non_contiguous_ledger_sequence() -> None:
    """Ledger sequence 缺口应明确暴露持久化状态损坏。"""

    with pytest.raises(InvalidLedger, match="连续且唯一"):
        rebuild_portfolio(
            make_user(),
            [make_transaction(sequence=2, action=TransactionAction.BUY, price="10", shares="1")],
        )


def test_normalizes_ticker_reason_and_timestamp() -> None:
    """Ledger Record 应保存规范化 Ticker、Reason 与 UTC 时间。"""

    transaction = Transaction.create(
        user_id=USER_ID,
        sequence=1,
        ticker=" brk.b ",
        action=TransactionAction.BUY,
        price=Decimal("100"),
        shares=Decimal("1"),
        position_type=PositionType.LONG_TERM,
        occurred_at=datetime(2026, 8, 20, 20, 0, tzinfo=UTC),
        reason="  建立长期仓  ",
    )

    assert transaction.ticker == "BRK.B"
    assert transaction.reason == "建立长期仓"
    assert transaction.occurred_at.tzinfo is UTC
