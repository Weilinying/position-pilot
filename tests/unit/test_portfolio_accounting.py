"""Portfolio 已实现收益聚合测试。"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from position_pilot.domain.portfolio import (
    LotAllocation,
    PositionLotSource,
    PositionReconciliation,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    replay_portfolio,
)
from position_pilot.domain.portfolio_accounting import calculate_portfolio_accounting

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def make_user() -> User:
    """创建固定测试 User。"""

    return User.create(
        user_id=USER_ID,
        display_name="测试用户",
        initial_cash=Decimal("1000"),
        created_at=BASE_TIME,
    )


def make_transaction(
    *,
    sequence: int,
    ticker: str,
    action: TransactionAction,
    price: str,
    shares: str,
    fee: str = "0",
    position_type: PositionType = PositionType.UNSPECIFIED,
    occurred_at: datetime = BASE_TIME,
) -> Transaction:
    """创建固定测试交易。"""

    return Transaction.create(
        user_id=USER_ID,
        sequence=sequence,
        ticker=ticker,
        action=action,
        price=Decimal(price),
        shares=Decimal(shares),
        fee=Decimal(fee),
        position_type=position_type,
        occurred_at=occurred_at,
    )


def make_allocation(transaction: Transaction, lot_id: UUID, shares: str) -> LotAllocation:
    """创建固定测试批次分配。"""

    return LotAllocation.create(
        user_id=USER_ID,
        sell_transaction_id=transaction.id,
        lot_id=lot_id,
        shares=Decimal(shares),
    )


def test_accounting_aggregates_realized_pnl_and_single_sell_percent() -> None:
    """单笔 SELL 应保留成交额、费用、净收入、释放成本和收益率。"""

    buy = make_transaction(
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price="100",
        shares="2",
    )
    sell = make_transaction(
        sequence=2,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price="120",
        shares="1",
        fee="1",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    replay = replay_portfolio(
        make_user(),
        [buy, sell],
        lot_allocations=[make_allocation(sell, buy.id, "1")],
    )

    accounting = calculate_portfolio_accounting(replay)

    assert accounting.metrics.gross_proceeds == Decimal("120.00000000")
    assert accounting.metrics.fee == Decimal("1.00000000")
    assert accounting.metrics.net_proceeds == Decimal("119.00000000")
    assert accounting.metrics.released_cost == Decimal("100.00000000")
    assert accounting.metrics.realized_pnl == Decimal("19.00000000")
    assert accounting.metrics.realized_pnl_percent == Decimal("19.00000000")
    assert len(accounting.transactions) == 1
    assert accounting.transactions[0].transaction_id == sell.id
    assert accounting.tickers[0].ticker == "GOOG"


def test_accounting_orders_transactions_descending_and_types_explicitly() -> None:
    """聚合应按交易倒序，并按 UNSPECIFIED、SWING、LONG_TERM 输出类型。"""

    unspecified_buy = make_transaction(
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price="100",
        shares="1",
    )
    swing_buy = make_transaction(
        sequence=2,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price="80",
        shares="1",
        position_type=PositionType.SWING,
    )
    long_term_buy = make_transaction(
        sequence=3,
        ticker="AAPL",
        action=TransactionAction.BUY,
        price="50",
        shares="1",
        position_type=PositionType.LONG_TERM,
    )
    goog_sell = make_transaction(
        sequence=4,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price="120",
        shares="2",
        fee="1",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    aapl_sell = make_transaction(
        sequence=5,
        ticker="AAPL",
        action=TransactionAction.SELL,
        price="40",
        shares="1",
        occurred_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
    replay = replay_portfolio(
        make_user(),
        [unspecified_buy, swing_buy, long_term_buy, goog_sell, aapl_sell],
        lot_allocations=[
            make_allocation(goog_sell, swing_buy.id, "1"),
            make_allocation(aapl_sell, long_term_buy.id, "1"),
            make_allocation(goog_sell, unspecified_buy.id, "1"),
        ],
    )

    accounting = calculate_portfolio_accounting(replay)

    assert [item.transaction_id for item in accounting.transactions] == [
        aapl_sell.id,
        goog_sell.id,
    ]
    assert [item.ticker for item in accounting.tickers] == ["AAPL", "GOOG"]
    goog_types = accounting.tickers[1].position_types
    assert [item.position_type for item in goog_types] == [
        PositionType.UNSPECIFIED,
        PositionType.SWING,
    ]
    assert accounting.metrics.gross_proceeds == Decimal("280.00000000")
    assert accounting.metrics.fee == Decimal("1.00000000")
    assert accounting.metrics.net_proceeds == Decimal("279.00000000")
    assert accounting.metrics.released_cost == Decimal("230.00000000")
    assert accounting.metrics.realized_pnl == Decimal("49.00000000")


def test_accounting_without_sell_has_zero_metrics_and_no_percent() -> None:
    """没有 SELL 时应返回零金额与空的收益率。"""

    buy = make_transaction(
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price="100",
        shares="1",
    )
    accounting = calculate_portfolio_accounting(replay_portfolio(make_user(), [buy]))

    assert accounting.metrics.realized_pnl == Decimal("0E-8")
    assert accounting.metrics.realized_pnl_percent is None
    assert accounting.transactions == ()
    assert accounting.tickers == ()


def test_accounting_keeps_fully_closed_ticker_in_history() -> None:
    """完全卖出的批次应从当前持仓消失，但仍保留收益明细。"""

    buy = make_transaction(
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price="100",
        shares="1",
    )
    sell = make_transaction(
        sequence=2,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price="120",
        shares="1",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    replay = replay_portfolio(
        make_user(),
        [buy, sell],
        lot_allocations=[make_allocation(sell, buy.id, "1")],
    )

    accounting = calculate_portfolio_accounting(replay)

    assert replay.portfolio.lots == ()
    assert [item.ticker for item in accounting.tickers] == ["GOOG"]
    assert accounting.transactions[0].metrics.realized_pnl == Decimal("20.00000000")


def test_accounting_reports_none_percent_for_zero_released_cost() -> None:
    """极小单位成本在现有量化规则下释放为零时，收益率保持为空。"""

    reconciliation = PositionReconciliation.create(
        user_id=USER_ID,
        ticker="GOOG",
        target_shares=Decimal("1"),
        target_average_cost=Decimal("0.00000001"),
        source="test",
        confirmed_at=BASE_TIME,
    )
    sell = make_transaction(
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price="1",
        shares="0.00000001",
        occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    replay = replay_portfolio(
        make_user(),
        [sell],
        reconciliations=[reconciliation],
        lot_allocations=[make_allocation(sell, reconciliation.id, "0.00000001")],
    )

    result = replay.sell_allocation_results[0]
    accounting = calculate_portfolio_accounting(replay)

    assert result.source is PositionLotSource.RECONCILIATION
    assert result.released_cost == Decimal("0E-8")
    assert accounting.metrics.released_cost == Decimal("0E-8")
    assert accounting.metrics.realized_pnl_percent is None
