"""Position Funding Snapshot 确定性语义测试。"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.position_funding import (
    PositionFundingSnapshot,
    PositionPlanIntent,
)
from position_pilot.domain.portfolio import (
    LotAllocation,
    PortfolioState,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 21, tzinfo=UTC)


def _transaction(
    sequence: int,
    action: TransactionAction,
    *,
    price: str,
    shares: str,
    position_type: PositionType = PositionType.LONG_TERM,
) -> Transaction:
    return Transaction.create(
        user_id=USER_ID,
        sequence=sequence,
        ticker="GOOG",
        action=action,
        price=Decimal(price),
        shares=Decimal(shares),
        position_type=position_type,
        occurred_at=NOW,
    )


def _portfolio(transactions: list[Transaction]) -> PortfolioState:
    user = User.create(
        user_id=USER_ID,
        display_name="Funding Test",
        initial_cash=Decimal("1000"),
        created_at=NOW,
    )
    return rebuild_portfolio(user, transactions, [])


def _intent(
    target: str = "300",
    position_type: PositionType = PositionType.LONG_TERM,
) -> PositionPlanIntent:
    return PositionPlanIntent("goog", position_type, Decimal(target))


def test_no_position_keeps_entire_target_budget_available() -> None:
    snapshot = PositionFundingSnapshot.from_portfolio(_portfolio([]), _intent())

    assert snapshot.open_quantity == 0
    assert snapshot.average_cost is None
    assert snapshot.open_cost_basis == 0
    assert snapshot.remaining_target_budget == Decimal("300")


def test_current_open_cost_basis_reduces_remaining_target_budget() -> None:
    state = _portfolio([_transaction(1, TransactionAction.BUY, price="80", shares="2")])

    snapshot = PositionFundingSnapshot.from_portfolio(state, _intent())

    assert snapshot.open_cost_basis == Decimal("160")
    assert snapshot.remaining_target_budget == Decimal("140")


def test_sell_releases_target_budget_space_from_current_open_cost_basis() -> None:
    buy = _transaction(1, TransactionAction.BUY, price="80", shares="2")
    sell = _transaction(2, TransactionAction.SELL, price="90", shares="1")
    state = rebuild_portfolio(
        User.create(
            user_id=USER_ID,
            display_name="Funding Test",
            initial_cash=Decimal("1000"),
            created_at=NOW,
        ),
        [buy, sell],
        [],
        lot_allocations=[
            LotAllocation.create(
                user_id=USER_ID,
                sell_transaction_id=sell.id,
                lot_id=buy.id,
                shares=Decimal("1"),
            )
        ],
    )

    snapshot = PositionFundingSnapshot.from_portfolio(state, _intent())

    assert snapshot.open_cost_basis == Decimal("80")
    assert snapshot.remaining_target_budget == Decimal("220")


def test_position_types_have_independent_target_scopes() -> None:
    state = _portfolio(
        [
            _transaction(1, TransactionAction.BUY, price="80", shares="2"),
            _transaction(
                2,
                TransactionAction.BUY,
                price="50",
                shares="1",
                position_type=PositionType.SWING,
            ),
        ]
    )

    long_term = PositionFundingSnapshot.from_portfolio(state, _intent())
    swing = PositionFundingSnapshot.from_portfolio(
        state,
        _intent("100", PositionType.SWING),
    )

    assert long_term.open_cost_basis == Decimal("160")
    assert long_term.remaining_target_budget == Decimal("140")
    assert swing.open_cost_basis == Decimal("50")
    assert swing.remaining_target_budget == Decimal("50")


def test_remaining_target_budget_floors_at_zero() -> None:
    state = _portfolio([_transaction(1, TransactionAction.BUY, price="200", shares="2")])

    snapshot = PositionFundingSnapshot.from_portfolio(state, _intent())

    assert snapshot.open_cost_basis == Decimal("400")
    assert snapshot.remaining_target_budget == 0
    assert snapshot.as_dict()["target_budget_semantics"] == ("CURRENT_POSITION_CAPITAL_ALLOCATION")


def test_position_plan_rejects_unspecified_position_type() -> None:
    with pytest.raises(ValueError, match="LONG_TERM 或 SWING"):
        _intent(position_type=PositionType.UNSPECIFIED)
