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
    CashEvent,
    CashEventType,
    LotAllocation,
    LotClassificationChange,
    OpeningPosition,
    PositionReconciliation,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    calculate_amount,
    calculate_commission,
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
    occurred_at: datetime = OCCURRED_AT,
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
        occurred_at=occurred_at,
    )


def make_allocation(transaction: Transaction, lot_id: UUID, shares: str) -> LotAllocation:
    """创建与测试 SELL 对应的明确批次分配。"""

    return LotAllocation.create(
        user_id=USER_ID,
        sell_transaction_id=transaction.id,
        lot_id=lot_id,
        shares=Decimal(shares),
    )


def make_cash_event(
    *,
    sequence: int,
    event_type: CashEventType,
    amount: str,
    occurred_at: datetime = OCCURRED_AT,
) -> CashEvent:
    """创建固定 User 的 Cash Event。"""

    return CashEvent.create(
        user_id=USER_ID,
        sequence=sequence,
        event_type=event_type,
        amount=Decimal(amount),
        occurred_at=occurred_at,
    )


def make_opening_position(
    *,
    ticker: str = "GOOG",
    shares: str = "2",
    average_cost: str = "100",
    position_type: PositionType | None = None,
    user_id: UUID = USER_ID,
) -> OpeningPosition:
    """创建不带经济顺序的固定 Opening Position。"""

    return OpeningPosition.create(
        user_id=user_id,
        ticker=ticker,
        shares=Decimal(shares),
        average_cost=Decimal(average_cost),
        position_type=position_type,
        recorded_at=OCCURRED_AT,
    )


def make_reconciliation(
    *,
    ticker: str = "GOOG",
    target_shares: str = "4",
    target_average_cost: str = "125",
    position_type: PositionType | None = None,
    confirmed_at: datetime = OCCURRED_AT,
    user_id: UUID = USER_ID,
) -> PositionReconciliation:
    """创建固定 User 的持仓校准事件。"""

    return PositionReconciliation.create(
        user_id=user_id,
        ticker=ticker,
        target_shares=Decimal(target_shares),
        target_average_cost=Decimal(target_average_cost),
        position_type=position_type,
        source="screenshot",
        confirmed_at=confirmed_at,
        broker="paper-broker",
    )


def test_transaction_amount_is_derived_and_not_a_create_input() -> None:
    """amount 与 commission 应只读派生，不能出现在 Transaction 写入参数中。"""

    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="220.5",
        shares="0.45",
    )

    assert transaction.amount == Decimal("99.22500000")
    assert transaction.commission == Decimal("0.99225000")
    assert "amount" not in signature(Transaction.create).parameters
    assert "commission" not in signature(Transaction.create).parameters
    assert calculate_amount(Decimal("220.5"), Decimal("0.45")) == Decimal("99.22500000")


def test_missing_position_type_is_explicitly_unspecified() -> None:
    """缺省仓位类型必须保存为明确事实，不得猜测投资意图。"""

    transaction = Transaction.create(
        user_id=USER_ID,
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("10"),
        shares=Decimal("1"),
        occurred_at=OCCURRED_AT,
    )
    opening_position = make_opening_position()

    assert transaction.position_type is PositionType.UNSPECIFIED
    assert opening_position.position_type is PositionType.UNSPECIFIED


def test_falsey_invalid_position_type_is_not_treated_as_missing() -> None:
    """只有 None 表示缺省；空字符串等非法运行时值不得静默归一。"""

    with pytest.raises(InvalidPortfolioValue, match="position_type"):
        Transaction.create(
            user_id=USER_ID,
            sequence=1,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("10"),
            shares=Decimal("1"),
            position_type="",  # type: ignore[arg-type]
            occurred_at=OCCURRED_AT,
        )
    with pytest.raises(InvalidPortfolioValue, match="position_type"):
        OpeningPosition.create(
            user_id=USER_ID,
            ticker="GOOG",
            shares=Decimal("1"),
            average_cost=Decimal("10"),
            position_type="",  # type: ignore[arg-type]
            recorded_at=OCCURRED_AT,
        )


def test_opening_position_derives_cost_basis_without_economic_sequence() -> None:
    """Opening Position 只保存起始事实，Cost Basis 由后端派生。"""

    opening_position = make_opening_position(shares="2.5", average_cost="123.45")

    assert opening_position.cost_basis == Decimal("308.62500000")
    assert "sequence" not in signature(OpeningPosition).parameters
    assert "cost_basis" not in signature(OpeningPosition.create).parameters


def test_replay_starts_from_opening_state_without_cash_impact() -> None:
    """Opening Position 建立起始成本与 Shares，但不得改变可用现金。"""

    opening_position = make_opening_position(shares="2", average_cost="100")
    state = rebuild_portfolio(make_user("500"), [], [], [opening_position])

    position = state.get_position("GOOG", PositionType.UNSPECIFIED)
    assert position is not None
    assert position.shares == Decimal("2.00000000")
    assert position.cost_basis == Decimal("200.00000000")
    assert position.average_cost == Decimal("100.00000000")
    assert state.cash.available_cash == Decimal("500.00000000")


def test_reconciliation_calibrates_position_without_cash_or_trade_effect() -> None:
    """持仓校准应直接替换目标 Position，但不产生交易或现金变化。"""

    opening_position = make_opening_position(shares="2", average_cost="100")
    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="10",
        shares="1",
        occurred_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
    )
    reconciliation = make_reconciliation(
        target_shares="7",
        target_average_cost="130",
        confirmed_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )

    state = rebuild_portfolio(
        make_user("500"),
        [transaction],
        [],
        [opening_position],
        [reconciliation],
    )

    position = state.get_position("GOOG", PositionType.UNSPECIFIED)
    assert position is not None
    assert position.shares == Decimal("7.00000000")
    assert position.average_cost == Decimal("130.00000000")
    assert state.cash.available_cash == Decimal("489.90000000")
    assert state.transaction_count == 1
    assert state.reconciliation_count == 1


def test_reconciliation_preserves_unmentioned_positions() -> None:
    """校准只覆盖对应 Position Key，截图未出现的持仓必须保留。"""

    opening_positions = [
        make_opening_position(ticker="GOOG", shares="2"),
        make_opening_position(ticker="MSFT", shares="3"),
    ]
    state = rebuild_portfolio(
        make_user(),
        [],
        [],
        opening_positions,
        [make_reconciliation(ticker="GOOG", target_shares="5")],
    )

    goog = state.get_position("GOOG", PositionType.UNSPECIFIED)
    msft = state.get_position("MSFT", PositionType.UNSPECIFIED)
    assert goog is not None and goog.shares == Decimal("5.00000000")
    assert msft is not None and msft.shares == Decimal("3.00000000")


def test_reconciliation_preserves_confirmed_average_cost_without_round_trip_drift() -> None:
    """校准均价不得经已量化 Cost Basis 反推后产生最小精度漂移。"""

    state = rebuild_portfolio(
        make_user(),
        [],
        [],
        [],
        [
            make_reconciliation(
                target_shares="0.3",
                target_average_cost="100.12345678",
            )
        ],
    )

    position = state.get_position("GOOG", PositionType.UNSPECIFIED)
    assert position is not None
    assert position.shares == Decimal("0.30000000")
    assert position.cost_basis == Decimal("30.03703703")
    assert position.average_cost == Decimal("100.12345678")


def test_reconciliation_is_applied_before_later_transaction() -> None:
    """校准后的后续交易必须继续作用在目标状态上。"""

    reconciliation = make_reconciliation(
        target_shares="7",
        target_average_cost="130",
        confirmed_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )
    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.SELL,
        price="150",
        shares="2",
        position_type=PositionType.UNSPECIFIED,
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )

    state = rebuild_portfolio(
        make_user(),
        [transaction],
        [],
        [],
        [reconciliation],
        [make_allocation(transaction, reconciliation.id, "2")],
    )

    position = state.get_position("GOOG", PositionType.UNSPECIFIED)
    assert position is not None
    assert position.shares == Decimal("5.00000000")
    assert position.average_cost == Decimal("130.00000000")
    assert state.cash.available_cash == Decimal("1299.65000000")


def test_three_position_types_remain_independent_during_replay() -> None:
    """同一 Ticker 的三类 Position Key 不得相互合并或提供 Shares。"""

    opening_positions = [
        make_opening_position(position_type=PositionType.LONG_TERM, shares="3"),
        make_opening_position(position_type=PositionType.SWING, shares="2"),
        make_opening_position(position_type=PositionType.UNSPECIFIED, shares="1"),
    ]
    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.SELL,
        price="120",
        shares="1",
        position_type=PositionType.SWING,
    )
    state = rebuild_portfolio(
        make_user(),
        [transaction],
        [],
        opening_positions,
        [],
        [make_allocation(transaction, opening_positions[1].id, "1")],
    )

    long_term = state.get_position("GOOG", PositionType.LONG_TERM)
    swing = state.get_position("GOOG", PositionType.SWING)
    unspecified = state.get_position("GOOG", PositionType.UNSPECIFIED)
    assert long_term is not None and long_term.shares == Decimal("3.00000000")
    assert swing is not None and swing.shares == Decimal("1.00000000")
    assert unspecified is not None and unspecified.shares == Decimal("1.00000000")


def test_lot_classification_change_moves_only_current_batch() -> None:
    """批次类型调整只移动该批剩余持仓，不改变现金或成本。"""

    buy = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="10",
        shares="5",
        position_type=PositionType.UNSPECIFIED,
    )
    change = LotClassificationChange.create(
        user_id=USER_ID,
        lot_id=buy.id,
        position_type=PositionType.SWING,
        effective_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )

    state = rebuild_portfolio(
        make_user(),
        [buy],
        lot_classification_changes=[change],
    )

    assert state.get_position("GOOG", PositionType.UNSPECIFIED) is None
    swing = state.get_position("GOOG", PositionType.SWING)
    assert swing is not None and swing.shares == Decimal("5.00000000")
    assert swing.cost_basis == Decimal("50.35000000")
    assert state.cash.available_cash == Decimal("949.65000000")
    assert state.lots[0].id == buy.id
    assert state.lots[0].position_type is PositionType.SWING


def test_sell_allocation_releases_cost_from_selected_batch() -> None:
    """指定批次卖出后，总体均价应由其他剩余批次重新计算。"""

    first = make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="2")
    second = make_transaction(sequence=2, action=TransactionAction.BUY, price="20", shares="3")
    sell = make_transaction(sequence=3, action=TransactionAction.SELL, price="25", shares="2")

    state = rebuild_portfolio(
        make_user(),
        [first, second, sell],
        lot_allocations=[make_allocation(sell, first.id, "2")],
    )

    position = state.get_position("GOOG", PositionType.LONG_TERM)
    assert position is not None
    assert position.shares == Decimal("3.00000000")
    assert position.average_cost == Decimal("20.11666667")
    assert [lot.id for lot in state.lots] == [second.id]


def test_rejects_invalid_opening_state_owner_and_duplicate_key() -> None:
    """Opening State 必须属于同一 User，且 Position Key 唯一。"""

    wrong_owner = make_opening_position(user_id=UUID("00000000-0000-0000-0000-000000000002"))
    with pytest.raises(InvalidLedger, match="其他 User"):
        rebuild_portfolio(make_user(), [], [], [wrong_owner])

    with pytest.raises(InvalidLedger, match="必须唯一"):
        rebuild_portfolio(
            make_user(),
            [],
            [],
            [make_opening_position(), make_opening_position(ticker=" goog ")],
        )


@pytest.mark.parametrize(
    ("price", "shares", "expected"),
    [
        ("100", "50", "0.35000000"),
        ("100", "200", "0.70000000"),
        ("0.2", "10", "0.02000000"),
        ("10", "0.5", "0.05000000"),
        ("0.75", "0.05", "0.01000000"),
    ],
)
def test_calculates_ibkr_tiered_first_band_commission(
    price: str,
    shares: str,
    expected: str,
) -> None:
    """整股最低/最高限制与小数股规则应确定性执行。"""

    amount = calculate_amount(Decimal(price), Decimal(shares))

    assert calculate_commission(amount, Decimal(shares)) == Decimal(expected)


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
    assert position.cost_basis == Decimal("500.70000000")
    assert position.average_cost == Decimal("16.69000000")
    assert state.cash.available_cash == Decimal("499.30000000")
    assert state.transaction_count == 2


def test_rebuilds_cash_adjustment_vertical_slice_to_1100() -> None:
    """Deposit、净交易现金流与 Withdrawal 应按实际时间稳定合并重放。"""

    buy = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="594.05940594",
        shares="0.5",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    sell = make_transaction(
        sequence=2,
        action=TransactionAction.SELL,
        price="404.04040404",
        shares="0.25",
        occurred_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
    state = rebuild_portfolio(
        make_user(),
        [buy, sell],
        [
            make_cash_event(
                sequence=1,
                event_type=CashEventType.DEPOSIT,
                amount="500",
                occurred_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
            ),
            make_cash_event(
                sequence=2,
                event_type=CashEventType.WITHDRAWAL,
                amount="200",
                occurred_at=datetime(2026, 8, 23, 12, 0, tzinfo=UTC),
            ),
        ],
        [],
        [],
        [make_allocation(sell, buy.id, "0.25")],
    )

    position = state.get_position("GOOG", PositionType.LONG_TERM)
    assert state.cash.available_cash == Decimal("1100.00000000")
    assert state.cash.total_deposits == Decimal("500.00000000")
    assert state.cash.total_withdrawals == Decimal("200.00000000")
    assert state.transaction_count == 2
    assert state.cash_event_count == 2
    assert position is not None
    assert position.shares == Decimal("0.25000000")


def test_cash_events_do_not_change_position_financials() -> None:
    """Cash Event 只能改变 Cash，不得改变 Shares、Cost Basis 或 Average Cost。"""

    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="10",
        shares="10",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    without_cash_events = rebuild_portfolio(make_user(), [transaction])
    with_cash_events = rebuild_portfolio(
        make_user(),
        [transaction],
        [
            make_cash_event(
                sequence=1,
                event_type=CashEventType.DEPOSIT,
                amount="500",
            )
        ],
    )

    assert with_cash_events.positions == without_cash_events.positions
    assert (
        with_cash_events.cash.available_cash - without_cash_events.cash.available_cash
        == Decimal("500.00000000")
    )


def test_withdrawal_rejects_insufficient_cash() -> None:
    """Withdrawal 不得令 Available Cash 变为负数。"""

    with pytest.raises(InsufficientCash) as error:
        rebuild_portfolio(
            make_user("100"),
            [],
            [
                make_cash_event(
                    sequence=1,
                    event_type=CashEventType.WITHDRAWAL,
                    amount="101",
                )
            ],
        )

    assert error.value.available == Decimal("100.00000000")
    assert error.value.required == Decimal("101.00000000")


def test_cash_event_rebuild_is_deterministic_and_uses_stable_same_time_order() -> None:
    """同一组 Ledger 重建必须稳定，且同时间 Cash Event 先于 BUY 生效。"""

    transaction = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="150",
        shares="1",
    )
    cash_event = make_cash_event(
        sequence=1,
        event_type=CashEventType.DEPOSIT,
        amount="100",
    )

    first = rebuild_portfolio(make_user("100"), [transaction], [cash_event])
    second = rebuild_portfolio(make_user("100"), [transaction], [cash_event])

    assert first == second
    assert first.cash.available_cash == Decimal("49.65000000")


@pytest.mark.parametrize("amount", ["0", "-1", "1.000000001"])
def test_rejects_invalid_cash_event_amount(amount: str) -> None:
    """Cash Event amount 必须是最多 8 位小数的正数。"""

    with pytest.raises(InvalidPortfolioValue):
        make_cash_event(sequence=1, event_type=CashEventType.DEPOSIT, amount=amount)


def test_rejects_unknown_cash_event_type_and_naive_timestamp() -> None:
    """未知类型与无时区发生时间不得进入 Cash Event Ledger。"""

    with pytest.raises(InvalidPortfolioValue, match="event_type"):
        CashEvent.create(
            user_id=USER_ID,
            sequence=1,
            event_type=cast(CashEventType, "DIVIDEND"),
            amount=Decimal("1"),
            occurred_at=OCCURRED_AT,
        )
    with pytest.raises(InvalidPortfolioValue, match="timestamp"):
        CashEvent.create(
            user_id=USER_ID,
            sequence=1,
            event_type=CashEventType.DEPOSIT,
            amount=Decimal("1"),
            occurred_at=datetime(2026, 8, 20, 12, 0),
        )


def test_cash_event_normalizes_reason_and_timestamp() -> None:
    """Cash Event 应保留规范化原因并把实际发生时间统一为 UTC。"""

    cash_event = CashEvent.create(
        user_id=USER_ID,
        sequence=1,
        event_type=CashEventType.DEPOSIT,
        amount=Decimal("1"),
        occurred_at=datetime.fromisoformat("2026-08-20T20:00:00+08:00"),
        reason="  追加投资预算  ",
    )

    assert cash_event.occurred_at == OCCURRED_AT
    assert cash_event.occurred_at.tzinfo is UTC
    assert cash_event.reason == "追加投资预算"


def test_rejects_invalid_cash_event_ledger_owner_and_sequence() -> None:
    """Cash Event Ledger 的所有者与 sequence 损坏必须明确暴露。"""

    wrong_owner = CashEvent.create(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        sequence=1,
        event_type=CashEventType.DEPOSIT,
        amount=Decimal("1"),
        occurred_at=OCCURRED_AT,
    )
    gap = make_cash_event(
        sequence=2,
        event_type=CashEventType.DEPOSIT,
        amount="1",
    )

    with pytest.raises(InvalidLedger, match="其他 User"):
        rebuild_portfolio(make_user(), [], [wrong_owner])
    with pytest.raises(InvalidLedger, match="Cash Event sequence"):
        rebuild_portfolio(make_user(), [], [gap])


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

    buy = make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="10")
    sell = make_transaction(sequence=2, action=TransactionAction.SELL, price="15", shares="4")
    state = rebuild_portfolio(
        make_user(),
        [buy, sell],
        lot_allocations=[make_allocation(sell, buy.id, "4")],
    )

    position = state.get_position("GOOG", PositionType.LONG_TERM)
    assert position is not None
    assert position.shares == Decimal("6.00000000")
    assert position.cost_basis == Decimal("60.21000000")
    assert position.average_cost == Decimal("10.03500000")
    assert state.cash.available_cash == Decimal("959.30000000")


def test_full_sell_removes_only_matching_position() -> None:
    """全部 SELL 应移除目标仓位，但保留同 Ticker 的另一 Position Type。"""

    long_buy = make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="5")
    swing_buy = make_transaction(
        sequence=2,
        action=TransactionAction.BUY,
        price="10",
        shares="3",
        position_type=PositionType.SWING,
    )
    sell = make_transaction(sequence=3, action=TransactionAction.SELL, price="12", shares="5")
    state = rebuild_portfolio(
        make_user(),
        [long_buy, swing_buy, sell],
        lot_allocations=[make_allocation(sell, long_buy.id, "5")],
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
    assert error.value.required == Decimal("120.35000000")


def test_sell_rejects_oversell_for_allocated_lot() -> None:
    """SELL 不得超过明确指定批次的剩余股数。"""

    buy = make_transaction(
        sequence=1,
        action=TransactionAction.BUY,
        price="10",
        shares="5",
        position_type=PositionType.SWING,
    )
    sell = make_transaction(
        sequence=2,
        action=TransactionAction.SELL,
        price="12",
        shares="6",
        position_type=PositionType.SWING,
    )
    with pytest.raises(InsufficientShares) as error:
        rebuild_portfolio(
            make_user(),
            [buy, sell],
            lot_allocations=[make_allocation(sell, buy.id, "6")],
        )

    assert error.value.available == Decimal("5.00000000")


def test_lot_allocation_must_reference_a_sell_transaction() -> None:
    """批次分配不能挂在 BUY 或不存在的交易上。"""

    buy = make_transaction(sequence=1, action=TransactionAction.BUY, price="10", shares="5")

    with pytest.raises(InvalidLedger, match="SELL Transaction"):
        rebuild_portfolio(
            make_user(),
            [buy],
            lot_allocations=[make_allocation(buy, buy.id, "1")],
        )


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
