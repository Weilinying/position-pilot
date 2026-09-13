"""Portfolio Application Service 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import signature
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from position_pilot.application.errors import OpeningStateSealed, UserNotFound
from position_pilot.application.portfolio_service import (
    ChangeLotClassificationCommand,
    CorrectBuyTransactionCommand,
    CreateUserCommand,
    InitializeOpeningPositionsCommand,
    LotAllocationInput,
    OpeningPositionInput,
    PortfolioService,
    PositionReconciliationInput,
    RecordCashEventCommand,
    RecordPositionReconciliationsCommand,
    RecordTransactionCommand,
)
from position_pilot.domain.errors import FutureTimestamp, InsufficientCash, InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    BUY_COST_INCLUDED_FEE_SCHEDULE,
    SELL_ACTUAL_FEE_SCHEDULE,
    BuyTransactionCorrection,
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
)

OCCURRED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakeStore:
    """跨 Unit of Work 保存已提交测试状态。"""

    users: dict[UUID, User] = field(default_factory=dict)
    opening_positions: dict[UUID, list[OpeningPosition]] = field(default_factory=dict)
    reconciliations: dict[UUID, list[PositionReconciliation]] = field(default_factory=dict)
    transactions: dict[UUID, list[Transaction]] = field(default_factory=dict)
    cash_events: dict[UUID, list[CashEvent]] = field(default_factory=dict)
    lot_allocations: dict[UUID, list[LotAllocation]] = field(default_factory=dict)
    classification_changes: dict[UUID, list[LotClassificationChange]] = field(default_factory=dict)
    buy_corrections: dict[UUID, list[BuyTransactionCorrection]] = field(default_factory=dict)
    lock_requests: list[UUID] = field(default_factory=list)
    commit_count: int = 0


class FakeUnitOfWork:
    """只实现 Portfolio Service 所需 Contract 的测试替身。"""

    def __init__(self, store: FakeStore) -> None:
        self._store = store

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None:
        if for_update:
            self._store.lock_requests.append(user_id)
        return self._store.users.get(user_id)

    def add_user(self, user: User) -> None:
        self._store.users[user.id] = user
        self._store.opening_positions[user.id] = []
        self._store.reconciliations[user.id] = []
        self._store.transactions[user.id] = []
        self._store.cash_events[user.id] = []
        self._store.lot_allocations[user.id] = []
        self._store.classification_changes[user.id] = []
        self._store.buy_corrections[user.id] = []

    def list_opening_positions(self, user_id: UUID) -> list[OpeningPosition]:
        return sorted(
            self._store.opening_positions[user_id],
            key=lambda position: (position.ticker, position.position_type.value),
        )

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None:
        if opening_positions:
            self._store.opening_positions[opening_positions[0].user_id].extend(opening_positions)

    def list_position_reconciliations(self, user_id: UUID) -> list[PositionReconciliation]:
        return sorted(
            self._store.reconciliations[user_id],
            key=lambda reconciliation: (reconciliation.confirmed_at, reconciliation.id.hex),
        )

    def add_position_reconciliation(self, reconciliation: PositionReconciliation) -> None:
        self._store.reconciliations[reconciliation.user_id].append(reconciliation)

    def list_lot_allocations(self, user_id: UUID) -> list[LotAllocation]:
        return list(self._store.lot_allocations[user_id])

    def add_lot_allocations(self, allocations: list[LotAllocation]) -> None:
        if allocations:
            self._store.lot_allocations[allocations[0].user_id].extend(allocations)

    def list_lot_classification_changes(
        self,
        user_id: UUID,
    ) -> list[LotClassificationChange]:
        return sorted(
            self._store.classification_changes[user_id],
            key=lambda change: (change.effective_at, change.id.hex),
        )

    def add_lot_classification_change(self, change: LotClassificationChange) -> None:
        self._store.classification_changes[change.user_id].append(change)

    def list_buy_transaction_corrections(
        self,
        user_id: UUID,
    ) -> list[BuyTransactionCorrection]:
        return list(self._store.buy_corrections[user_id])

    def add_buy_transaction_correction(self, correction: BuyTransactionCorrection) -> None:
        self._store.buy_corrections[correction.user_id].append(correction)

    def list_transactions(self, user_id: UUID) -> list[Transaction]:
        return sorted(
            self._store.transactions[user_id],
            key=lambda transaction: transaction.sequence,
        )

    def add_transaction(self, transaction: Transaction) -> None:
        self._store.transactions[transaction.user_id].append(transaction)

    def list_cash_events(self, user_id: UUID) -> list[CashEvent]:
        return sorted(self._store.cash_events[user_id], key=lambda event: event.sequence)

    def add_cash_event(self, cash_event: CashEvent) -> None:
        self._store.cash_events[cash_event.user_id].append(cash_event)

    def synchronize_sequences(self, transactions: list[Transaction]) -> None:
        """用重新派生的 Transaction 替换已存在记录。"""

        if not transactions:
            return
        user_id = transactions[0].user_id
        replacements = {transaction.id: transaction for transaction in transactions}
        self._store.transactions[user_id] = [
            replacements.get(transaction.id, transaction)
            for transaction in self._store.transactions[user_id]
        ]

    def synchronize_cash_event_sequences(self, cash_events: list[CashEvent]) -> None:
        """用重新派生的 Cash Event 替换已存在记录。"""

        if not cash_events:
            return
        user_id = cash_events[0].user_id
        replacements = {event.id: event for event in cash_events}
        self._store.cash_events[user_id] = [
            replacements.get(event.id, event) for event in self._store.cash_events[user_id]
        ]

    def commit(self) -> None:
        self._store.commit_count += 1


class FakeUnitOfWorkFactory:
    """为每次调用返回共享 Store 的新 Unit of Work。"""

    def __init__(self, store: FakeStore) -> None:
        self._store = store

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self._store)


def make_service() -> tuple[PortfolioService, FakeStore]:
    """创建共享内存状态的 Service。"""

    store = FakeStore()
    return PortfolioService(FakeUnitOfWorkFactory(store), clock=lambda: NOW), store


def test_record_command_accepts_fee_but_not_derived_fields() -> None:
    """用户可提交实际费用，但不能提交只读金额或 commission。"""

    assert "amount" not in signature(RecordTransactionCommand).parameters
    assert "commission" not in signature(RecordTransactionCommand).parameters
    assert "fee" in signature(RecordTransactionCommand).parameters
    assert "sequence" not in signature(RecordTransactionCommand).parameters


def test_cash_event_command_does_not_accept_ledger_identity_or_sequence() -> None:
    """Cash Event ID 与 sequence 必须由系统产生，不能由调用方指定。"""

    assert "id" not in signature(RecordCashEventCommand).parameters
    assert "cash_event_id" not in signature(RecordCashEventCommand).parameters
    assert "sequence" not in signature(RecordCashEventCommand).parameters


def test_creates_user_and_recovers_initial_cash() -> None:
    """新 User 应持久化 Initial Cash 并可恢复空 Portfolio。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="  Alice  ", initial_cash=Decimal("1000"))
    )

    state = service.get_portfolio(user.id)

    assert user.display_name == "Alice"
    assert state.cash.initial_cash == Decimal("1000.00000000")
    assert state.cash.available_cash == Decimal("1000.00000000")
    assert state.positions == ()
    assert store.commit_count == 1


def test_records_transactions_with_included_buy_cost() -> None:
    """写入应锁定 User，并把新 BUY 价格直接作为含费平均成本。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    first = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="goog",
            action=TransactionAction.BUY,
            price=Decimal("220.5"),
            shares=Decimal("0.45"),
            position_type=PositionType.LONG_TERM,
            occurred_at=OCCURRED_AT,
            reason="首次建仓",
        )
    )
    second = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("1"),
            position_type=PositionType.SWING,
            occurred_at=OCCURRED_AT,
        )
    )

    recovered = PortfolioService(FakeUnitOfWorkFactory(store)).get_portfolio(user.id)

    assert first.sequence == 1
    assert first.amount == Decimal("99.22500000")
    assert first.commission == Decimal("0E-8")
    assert first.fee_schedule == BUY_COST_INCLUDED_FEE_SCHEDULE
    assert second.sequence == 2
    assert store.lock_requests == [user.id, user.id]
    assert recovered.transaction_count == 2
    assert len(recovered.positions) == 2
    assert recovered.cash.available_cash == Decimal("800.77500000")


def test_transaction_without_occurred_at_uses_application_clock() -> None:
    """省略交易时间时只能使用可注入的 Application Clock。"""

    service, _ = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    transaction = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("10"),
            shares=Decimal("1"),
            position_type=PositionType.LONG_TERM,
        )
    )

    assert transaction.occurred_at == NOW


def test_future_transaction_is_rejected_before_ledger_read_or_persistence() -> None:
    """尚未发生的交易不得提前改变当前 Portfolio。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    with pytest.raises(FutureTimestamp, match="occurred_at 不得晚于当前时间"):
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("10"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
                occurred_at=NOW + timedelta(seconds=1),
            )
        )

    assert service.list_transactions(user.id) == ()
    assert store.lock_requests == [user.id]
    assert store.commit_count == 1


def test_transaction_normalizes_explicit_offset_time_to_utc() -> None:
    """历史补录可使用明确 Offset，但持久化语义统一为 UTC。"""

    service, _ = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    transaction = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("10"),
            shares=Decimal("1"),
            position_type=PositionType.LONG_TERM,
            occurred_at=datetime.fromisoformat("2026-08-20T20:00:00+08:00"),
        )
    )

    assert transaction.occurred_at == OCCURRED_AT
    assert transaction.occurred_at.tzinfo is UTC


def test_get_investment_context_projects_history_from_same_ledger_read() -> None:
    """Agent Context 应同时返回派生 Portfolio 与当前仓位的历史 BUY Facts。"""

    service, _ = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )
    service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("200"),
            shares=Decimal("1"),
            position_type=PositionType.LONG_TERM,
            occurred_at=OCCURRED_AT,
        )
    )
    service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("220"),
            shares=Decimal("1"),
            position_type=PositionType.SWING,
            occurred_at=OCCURRED_AT + timedelta(days=1),
        )
    )

    context = service.get_investment_context(user.id)

    assert len(context.portfolio.positions) == 2
    assert context.portfolio.transaction_count == 2
    assert [record.price for record in context.historical_buy_facts.records] == [
        Decimal("200.00000000"),
        Decimal("220.00000000"),
    ]
    assert [record.position_type for record in context.historical_buy_facts.records] == [
        PositionType.LONG_TERM,
        PositionType.SWING,
    ]


def test_records_cash_events_with_lock_and_rebuilds_available_cash() -> None:
    """Cash Event 写入应锁定 User，并返回同事务重建后的现金状态。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    deposit = service.record_cash_event(
        RecordCashEventCommand(
            user_id=user.id,
            event_type=CashEventType.DEPOSIT,
            amount=Decimal("500"),
            occurred_at=OCCURRED_AT,
            reason="追加投资预算",
        )
    )
    withdrawal = service.record_cash_event(
        RecordCashEventCommand(
            user_id=user.id,
            event_type=CashEventType.WITHDRAWAL,
            amount=Decimal("200"),
            occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        )
    )

    state = service.get_portfolio(user.id)

    assert deposit.cash_event.amount == Decimal("500.00000000")
    assert deposit.portfolio.cash.available_cash == Decimal("1500.00000000")
    assert withdrawal.portfolio.cash.available_cash == Decimal("1300.00000000")
    assert state.cash.total_deposits == Decimal("500.00000000")
    assert state.cash.total_withdrawals == Decimal("200.00000000")
    assert state.cash_event_count == 2
    assert store.lock_requests == [user.id, user.id]
    assert store.commit_count == 3


def test_cash_event_without_occurred_at_uses_application_clock() -> None:
    """省略现金事件时间时使用同一个 Application Clock。"""

    service, _ = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )

    result = service.record_cash_event(
        RecordCashEventCommand(
            user_id=user.id,
            event_type=CashEventType.DEPOSIT,
            amount=Decimal("500"),
        )
    )

    assert result.cash_event.occurred_at == NOW


def test_failed_withdrawal_is_not_added_or_committed() -> None:
    """超额 Withdrawal 必须在 Ledger 追加与 Commit 前失败。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("100")))

    with pytest.raises(InsufficientCash) as error:
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.WITHDRAWAL,
                amount=Decimal("101"),
                occurred_at=OCCURRED_AT,
            )
        )

    assert error.value.available == Decimal("100.00000000")
    assert service.list_cash_events(user.id) == ()
    assert store.commit_count == 1


def test_future_cash_event_is_rejected_before_ledger_read_or_persistence() -> None:
    """尚未实际发生的现金调整不得提前进入当前 Available Cash。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("100")))

    with pytest.raises(FutureTimestamp, match="occurred_at 不得晚于当前时间"):
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("500"),
                occurred_at=NOW + timedelta(seconds=1),
            )
        )

    assert service.get_portfolio(user.id).cash.available_cash == Decimal("100.00000000")
    assert service.list_cash_events(user.id) == ()
    assert store.lock_requests == [user.id]
    assert store.commit_count == 1


def test_backdated_cash_event_resequences_independent_ledger() -> None:
    """Cash Event 历史补录应重新派生自身 sequence。"""

    service, _ = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("100")))
    later = service.record_cash_event(
        RecordCashEventCommand(
            user_id=user.id,
            event_type=CashEventType.DEPOSIT,
            amount=Decimal("20"),
            occurred_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        )
    )
    earlier = service.record_cash_event(
        RecordCashEventCommand(
            user_id=user.id,
            event_type=CashEventType.DEPOSIT,
            amount=Decimal("10"),
            occurred_at=OCCURRED_AT,
        )
    )

    cash_events = service.list_cash_events(user.id)

    assert earlier.cash_event.sequence == 1
    assert [(event.id, event.sequence) for event in cash_events] == [
        (earlier.cash_event.id, 1),
        (later.cash_event.id, 2),
    ]


def test_backdated_transaction_resequences_by_economic_time() -> None:
    """历史补录应移动后续经济序号，而不是追加到数据库顺序末尾。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )
    later = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("10"),
            shares=Decimal("1"),
            position_type=PositionType.LONG_TERM,
            occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        )
    )
    earlier = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("20"),
            shares=Decimal("1"),
            position_type=PositionType.LONG_TERM,
            occurred_at=OCCURRED_AT,
        )
    )

    transactions = service.list_transactions(user.id)

    assert earlier.sequence == 1
    assert [(transaction.id, transaction.sequence) for transaction in transactions] == [
        (earlier.id, 1),
        (later.id, 2),
    ]
    assert store.commit_count == 3


def test_failed_transaction_is_not_added_or_committed() -> None:
    """领域校验失败必须发生在 Ledger 追加和 Commit 之前。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("100")))

    with pytest.raises(InsufficientCash):
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("101"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
            )
        )

    assert service.list_transactions(user.id) == ()
    assert store.commit_count == 1


@pytest.mark.parametrize("operation", ["portfolio", "transactions", "cash_events"])
def test_read_operations_reject_unknown_user(operation: str) -> None:
    """未知 User 必须产生明确 Application Error。"""

    service, _ = make_service()
    user_id = uuid4()

    with pytest.raises(UserNotFound) as error:
        if operation == "portfolio":
            service.get_portfolio(user_id)
        elif operation == "transactions":
            service.list_transactions(user_id)
        else:
            service.list_cash_events(user_id)

    assert error.value.user_id == user_id


def test_record_transaction_rejects_unknown_user() -> None:
    """未知 User 不得创建孤立 Ledger Record。"""

    service, store = make_service()
    user_id = uuid4()

    with pytest.raises(UserNotFound):
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user_id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("10"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
            )
        )

    assert store.transactions == {}
    assert store.commit_count == 0


def test_record_cash_event_rejects_unknown_user() -> None:
    """未知 User 不得创建孤立 Cash Event。"""

    service, store = make_service()

    with pytest.raises(UserNotFound):
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=uuid4(),
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("10"),
                occurred_at=NOW + timedelta(days=1),
            )
        )

    assert store.cash_events == {}
    assert store.commit_count == 0


def test_initializes_opening_state_once_with_stable_order_and_no_cash_impact() -> None:
    """Opening State 应在 User Lock 内原子写入，并按 Position Key 返回。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("500")))

    positions = service.initialize_opening_positions(
        InitializeOpeningPositionsCommand(
            user_id=user.id,
            positions=(
                OpeningPositionInput(
                    ticker="MSFT",
                    shares=Decimal("1"),
                    average_cost=Decimal("400"),
                    position_type=PositionType.LONG_TERM,
                ),
                OpeningPositionInput(
                    ticker="goog",
                    shares=Decimal("2"),
                    average_cost=Decimal("100"),
                ),
            ),
        )
    )

    assert [(position.ticker, position.position_type) for position in positions] == [
        ("GOOG", PositionType.UNSPECIFIED),
        ("MSFT", PositionType.LONG_TERM),
    ]
    assert all(position.recorded_at == NOW for position in positions)
    assert store.lock_requests[-1] == user.id
    assert store.commit_count == 2
    assert service.list_opening_positions(user.id) == positions
    assert service.get_portfolio(user.id).cash.available_cash == Decimal("500.00000000")


def test_records_position_reconciliation_as_immutable_event_without_cash_mutation() -> None:
    """Service 应追加校准事件，并保持 Cash 与未覆盖 Position 不变。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("500")))
    service.initialize_opening_positions(
        InitializeOpeningPositionsCommand(
            user_id=user.id,
            positions=(
                OpeningPositionInput(
                    ticker="GOOG",
                    shares=Decimal("2"),
                    average_cost=Decimal("100"),
                ),
                OpeningPositionInput(
                    ticker="MSFT",
                    shares=Decimal("3"),
                    average_cost=Decimal("200"),
                ),
            ),
        )
    )

    result = service.record_position_reconciliations(
        RecordPositionReconciliationsCommand(
            user_id=user.id,
            positions=(
                PositionReconciliationInput(
                    ticker="GOOG",
                    target_shares=Decimal("5"),
                    target_average_cost=Decimal("125"),
                ),
            ),
            source="screenshot",
            broker="paper-broker",
        )
    )

    recovered = service.get_portfolio(user.id)
    goog = recovered.get_position("GOOG", PositionType.UNSPECIFIED)
    msft = recovered.get_position("MSFT", PositionType.UNSPECIFIED)
    assert result.reconciliations[0].source == "screenshot"
    assert goog is not None and goog.shares == Decimal("5.00000000")
    assert goog.average_cost == Decimal("125.00000000")
    assert msft is not None and msft.shares == Decimal("3.00000000")
    assert recovered.cash.available_cash == Decimal("500.00000000")
    assert recovered.transaction_count == 0
    assert recovered.reconciliation_count == 1
    assert service.list_position_reconciliations(user.id) == result.reconciliations
    assert store.commit_count == 3


def test_reconciliation_rejects_overwriting_detailed_buy_lots() -> None:
    """汇总校准不能覆盖购买批次及其交易历史。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("500")))
    service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("2"),
        )
    )

    with pytest.raises(InvalidPortfolioValue, match="详细购买批次"):
        service.record_position_reconciliations(
            RecordPositionReconciliationsCommand(
                user_id=user.id,
                positions=(
                    PositionReconciliationInput(
                        ticker="GOOG",
                        target_shares=Decimal("3"),
                        target_average_cost=Decimal("110"),
                    ),
                ),
                source="manual",
            )
        )

    assert store.reconciliations[user.id] == []
    assert store.commit_count == 2


def test_opening_state_rejects_duplicate_normalized_position_key_atomically() -> None:
    """重复 Key 必须在持久化前失败，不能产生部分 Opening State。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("0")))

    with pytest.raises(InvalidPortfolioValue, match="不能包含重复"):
        service.initialize_opening_positions(
            InitializeOpeningPositionsCommand(
                user_id=user.id,
                positions=(
                    OpeningPositionInput(
                        ticker="GOOG",
                        shares=Decimal("1"),
                        average_cost=Decimal("100"),
                    ),
                    OpeningPositionInput(
                        ticker=" goog ",
                        shares=Decimal("2"),
                        average_cost=Decimal("110"),
                        position_type=PositionType.UNSPECIFIED,
                    ),
                ),
            )
        )

    assert store.opening_positions[user.id] == []
    assert store.commit_count == 1


@pytest.mark.parametrize(
    "existing_fact",
    ["opening", "transaction", "cash_event", "reconciliation"],
)
def test_opening_state_is_sealed_by_any_existing_portfolio_fact(existing_fact: str) -> None:
    """任何已有 Portfolio Fact 都必须封闭 Opening State 初始化。"""

    service, _ = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )
    opening_command = InitializeOpeningPositionsCommand(
        user_id=user.id,
        positions=(
            OpeningPositionInput(
                ticker="GOOG",
                shares=Decimal("1"),
                average_cost=Decimal("100"),
            ),
        ),
    )
    if existing_fact == "opening":
        service.initialize_opening_positions(opening_command)
    elif existing_fact == "transaction":
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("100"),
                shares=Decimal("1"),
            )
        )
    elif existing_fact == "cash_event":
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("100"),
            )
        )
    else:
        service.record_position_reconciliations(
            RecordPositionReconciliationsCommand(
                user_id=user.id,
                positions=(
                    PositionReconciliationInput(
                        ticker="GOOG",
                        target_shares=Decimal("1"),
                        target_average_cost=Decimal("100"),
                    ),
                ),
                source="screenshot",
            )
        )

    with pytest.raises(OpeningStateSealed):
        service.initialize_opening_positions(opening_command)


def test_unspecified_transaction_replays_against_unspecified_opening_position() -> None:
    """缺省 SELL 只能减少缺省归一后的 UNSPECIFIED 起始仓位。"""

    service, _ = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("0")))
    opening_positions = service.initialize_opening_positions(
        InitializeOpeningPositionsCommand(
            user_id=user.id,
            positions=(
                OpeningPositionInput(
                    ticker="GOOG",
                    shares=Decimal("2"),
                    average_cost=Decimal("100"),
                ),
            ),
        )
    )

    transaction = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.SELL,
            price=Decimal("120"),
            shares=Decimal("1"),
            fee=Decimal("1.25"),
            allocations=(LotAllocationInput(lot_id=opening_positions[0].id, shares=Decimal("1")),),
        )
    )

    position = service.get_portfolio(user.id).get_position("GOOG", PositionType.UNSPECIFIED)
    assert transaction.position_type is PositionType.UNSPECIFIED
    assert transaction.fee_schedule == SELL_ACTUAL_FEE_SCHEDULE
    assert transaction.commission == Decimal("1.25000000")
    assert position is not None and position.shares == Decimal("1.00000000")
    assert service.get_portfolio(user.id).cash.available_cash == Decimal("118.75000000")


def test_changes_current_lot_type_without_changing_cash_or_cost() -> None:
    """整批分类只移动当前批次，不应制造交易或现金变化。"""

    service, store = make_service()
    user = service.create_user(CreateUserCommand(display_name="Alice", initial_cash=Decimal("500")))
    purchase = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("2"),
        )
    )
    before = service.get_portfolio(user.id)

    result = service.change_lot_classification(
        ChangeLotClassificationCommand(
            user_id=user.id,
            lot_id=purchase.id,
            position_type=PositionType.SWING,
        )
    )

    assert result.portfolio.cash == before.cash
    assert result.portfolio.transaction_count == 1
    assert result.portfolio.lots[0].position_type is PositionType.SWING
    assert result.portfolio.lots[0].cost_basis == before.lots[0].cost_basis
    assert (
        service.get_investment_context(user.id).historical_buy_facts.records[0].position_type
        is PositionType.SWING
    )
    assert len(store.classification_changes[user.id]) == 1


def test_corrects_buy_by_appending_fact_and_replaying_current_lot() -> None:
    """BUY 更正应保留原交易，并更新现金、批次数量、成本和购买时间。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Alice", initial_cash=Decimal("1000"))
    )
    purchase = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("2"),
            position_type=PositionType.LONG_TERM,
            occurred_at=OCCURRED_AT,
        )
    )
    corrected_time = OCCURRED_AT + timedelta(days=1)

    result = service.correct_buy_transaction(
        CorrectBuyTransactionCommand(
            user_id=user.id,
            transaction_id=purchase.id,
            price=Decimal("120"),
            shares=Decimal("3"),
            occurred_at=corrected_time,
            reason="修正券商成交记录",
        )
    )

    assert len(store.transactions[user.id]) == 1
    assert store.transactions[user.id][0] == purchase
    assert len(store.buy_corrections[user.id]) == 1
    assert result.portfolio.lots[0].remaining_shares == Decimal("3.00000000")
    assert result.portfolio.lots[0].purchased_at == corrected_time
    assert result.portfolio.cash.available_cash == Decimal("640.00000000")


def test_accounting_reads_complete_facts_and_recalculates_after_correction() -> None:
    """核算读取和持仓复用同一重放，更正后历史卖出成本随有效 BUY 变化。"""

    service, store = make_service()
    user = service.create_user(
        CreateUserCommand(display_name="Accounting", initial_cash=Decimal("2000"))
    )
    buy = service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("10"),
            occurred_at=OCCURRED_AT,
        )
    )
    service.record_transaction(
        RecordTransactionCommand(
            user_id=user.id,
            ticker="GOOG",
            action=TransactionAction.SELL,
            price=Decimal("120"),
            shares=Decimal("4"),
            fee=Decimal("1"),
            occurred_at=OCCURRED_AT + timedelta(days=1),
            allocations=(LotAllocationInput(lot_id=buy.id, shares=Decimal("4")),),
        )
    )
    commits_before_read = store.commit_count
    assert service.get_accounting(user.id).metrics.realized_pnl == Decimal("79")
    replay = service.get_replay(user.id)
    assert service.get_portfolio(user.id) == replay.portfolio
    assert len(replay.sell_allocation_results) == 1
    assert store.commit_count == commits_before_read
    service.correct_buy_transaction(
        CorrectBuyTransactionCommand(
            user_id=user.id,
            transaction_id=buy.id,
            price=Decimal("105"),
            shares=Decimal("10"),
            occurred_at=OCCURRED_AT,
        )
    )
    assert service.get_accounting(user.id).metrics.realized_pnl == Decimal("59")
    assert store.transactions[user.id][0] == buy
