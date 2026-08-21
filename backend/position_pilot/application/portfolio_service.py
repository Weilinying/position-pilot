"""Portfolio Application Service。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from position_pilot.application.errors import UserNotFound
from position_pilot.domain.portfolio import (
    PortfolioState,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
    resequence_transactions,
)


class PortfolioUnitOfWork(Protocol):
    """Portfolio Service 所需的最小持久化事务边界。"""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None: ...

    def add_user(self, user: User) -> None: ...

    def list_transactions(self, user_id: UUID) -> list[Transaction]: ...

    def add_transaction(self, transaction: Transaction) -> None: ...

    def synchronize_sequences(self, transactions: list[Transaction]) -> None: ...

    def commit(self) -> None: ...


PortfolioUnitOfWorkFactory = Callable[[], PortfolioUnitOfWork]


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    """创建 Portfolio User 所需的输入。"""

    display_name: str
    initial_cash: Decimal


@dataclass(frozen=True, slots=True)
class RecordTransactionCommand:
    """追加 Ledger Transaction 的输入，amount 不属于用户输入。"""

    user_id: UUID
    ticker: str
    action: TransactionAction
    price: Decimal
    shares: Decimal
    position_type: PositionType
    occurred_at: datetime | None = None
    reason: str | None = None


class PortfolioService:
    """协调领域计算与 Portfolio 持久化事务。"""

    def __init__(self, unit_of_work_factory: PortfolioUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def create_user(self, command: CreateUserCommand) -> User:
        """创建带 Initial Cash 的 User。"""

        user = User.create(
            display_name=command.display_name,
            initial_cash=command.initial_cash,
        )
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.add_user(user)
            unit_of_work.commit()
        return user

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction:
        """锁定 User、校验当前 State 并原子追加 Transaction。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            transactions = unit_of_work.list_transactions(user.id)
            # 重新派生顺序前先验证已持久化 Ledger，避免意外掩盖 sequence 损坏。
            rebuild_portfolio(user, transactions)
            transaction = Transaction.create(
                user_id=user.id,
                sequence=len(transactions) + 1,
                ticker=command.ticker,
                action=command.action,
                price=command.price,
                shares=command.shares,
                position_type=command.position_type,
                occurred_at=command.occurred_at,
                reason=command.reason,
            )

            # sequence 是经济顺序的只读投影；历史补录会移动其后的派生序号。
            ordered_transactions = resequence_transactions([*transactions, transaction])
            rebuild_portfolio(user, ordered_transactions)
            persisted_transaction = next(
                candidate for candidate in ordered_transactions if candidate.id == transaction.id
            )
            persisted_by_id = {candidate.id: candidate for candidate in transactions}
            existing_transactions = [
                candidate for candidate in ordered_transactions if candidate.id != transaction.id
            ]
            if any(
                candidate.sequence != persisted_by_id[candidate.id].sequence
                for candidate in existing_transactions
            ):
                unit_of_work.synchronize_sequences(existing_transactions)
            unit_of_work.add_transaction(persisted_transaction)
            unit_of_work.commit()
            return persisted_transaction

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        """从持久化 Ledger 恢复当前 Portfolio State。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            transactions = unit_of_work.list_transactions(user.id)
            return rebuild_portfolio(user, transactions)

    def list_transactions(self, user_id: UUID) -> tuple[Transaction, ...]:
        """按 Ledger sequence 返回可追溯 Transaction。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_transactions(user.id))
