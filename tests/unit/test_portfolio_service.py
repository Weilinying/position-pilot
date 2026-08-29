"""Portfolio Application Service 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import signature
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from position_pilot.application.errors import UserNotFound
from position_pilot.application.portfolio_service import (
    CreateUserCommand,
    PortfolioService,
    RecordCashEventCommand,
    RecordTransactionCommand,
)
from position_pilot.domain.errors import InsufficientCash, InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    CashEvent,
    CashEventType,
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
    transactions: dict[UUID, list[Transaction]] = field(default_factory=dict)
    cash_events: dict[UUID, list[CashEvent]] = field(default_factory=dict)
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
        self._store.transactions[user.id] = []
        self._store.cash_events[user.id] = []

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


def test_record_command_does_not_accept_amount() -> None:
    """用户写入 Command 必须从结构上排除所有只读派生字段。"""

    assert "amount" not in signature(RecordTransactionCommand).parameters
    assert "commission" not in signature(RecordTransactionCommand).parameters
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


def test_records_transactions_with_lock_and_derived_financial_fields() -> None:
    """写入应锁定 User，并派生经济顺序、金额与佣金。"""

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
    assert first.commission == Decimal("0.99225000")
    assert second.sequence == 2
    assert store.lock_requests == [user.id, user.id]
    assert recovered.transaction_count == 2
    assert len(recovered.positions) == 2
    assert recovered.cash.available_cash == Decimal("799.43275000")


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

    with pytest.raises(InvalidPortfolioValue, match="occurred_at 不得晚于当前时间"):
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

    with pytest.raises(InvalidPortfolioValue, match="occurred_at 不得晚于当前时间"):
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
