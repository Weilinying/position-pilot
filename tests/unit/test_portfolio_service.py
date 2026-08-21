"""Portfolio Application Service 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    RecordTransactionCommand,
)
from position_pilot.domain.errors import InsufficientCash
from position_pilot.domain.portfolio import PositionType, Transaction, TransactionAction, User

OCCURRED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakeStore:
    """跨 Unit of Work 保存已提交测试状态。"""

    users: dict[UUID, User] = field(default_factory=dict)
    transactions: dict[UUID, list[Transaction]] = field(default_factory=dict)
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

    def list_transactions(self, user_id: UUID) -> list[Transaction]:
        return sorted(
            self._store.transactions[user_id],
            key=lambda transaction: transaction.sequence,
        )

    def add_transaction(self, transaction: Transaction) -> None:
        self._store.transactions[transaction.user_id].append(transaction)

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
    return PortfolioService(FakeUnitOfWorkFactory(store)), store


def test_record_command_does_not_accept_amount() -> None:
    """用户写入 Command 必须从结构上排除所有只读派生字段。"""

    assert "amount" not in signature(RecordTransactionCommand).parameters
    assert "commission" not in signature(RecordTransactionCommand).parameters
    assert "sequence" not in signature(RecordTransactionCommand).parameters


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


@pytest.mark.parametrize("operation", ["portfolio", "transactions"])
def test_read_operations_reject_unknown_user(operation: str) -> None:
    """未知 User 必须产生明确 Application Error。"""

    service, _ = make_service()
    user_id = uuid4()

    with pytest.raises(UserNotFound) as error:
        if operation == "portfolio":
            service.get_portfolio(user_id)
        else:
            service.list_transactions(user_id)

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
