"""Portfolio Application Service。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from position_pilot.application.errors import UserNotFound
from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    CashEvent,
    CashEventType,
    PortfolioState,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    normalize_timestamp,
    rebuild_portfolio,
    resequence_cash_events,
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

    def list_cash_events(self, user_id: UUID) -> list[CashEvent]: ...

    def add_cash_event(self, cash_event: CashEvent) -> None: ...

    def synchronize_cash_event_sequences(self, cash_events: list[CashEvent]) -> None: ...

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


@dataclass(frozen=True, slots=True)
class RecordCashEventCommand:
    """追加 Cash Event Ledger Record 的显式输入。"""

    user_id: UUID
    event_type: CashEventType
    amount: Decimal
    occurred_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CashAdjustmentResult:
    """同一事务内产生的 Cash Event 与重建后 Portfolio。"""

    cash_event: CashEvent
    portfolio: PortfolioState


class PortfolioService:
    """协调领域计算与 Portfolio 持久化事务。"""

    def __init__(
        self,
        unit_of_work_factory: PortfolioUnitOfWorkFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))

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

            current_time = normalize_timestamp(self._clock())
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise InvalidPortfolioValue("Transaction occurred_at 不得晚于当前时间")

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            # 重新派生顺序前先验证已持久化 Ledger，避免意外掩盖 sequence 损坏。
            rebuild_portfolio(user, transactions, cash_events)
            transaction = Transaction.create(
                user_id=user.id,
                sequence=len(transactions) + 1,
                ticker=command.ticker,
                action=command.action,
                price=command.price,
                shares=command.shares,
                position_type=command.position_type,
                occurred_at=occurred_at,
                reason=command.reason,
            )

            # sequence 是经济顺序的只读投影；历史补录会移动其后的派生序号。
            ordered_transactions = resequence_transactions([*transactions, transaction])
            rebuild_portfolio(user, ordered_transactions, cash_events)
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

    def record_cash_event(self, command: RecordCashEventCommand) -> CashAdjustmentResult:
        """锁定 User、校验完整 State 并原子追加 Cash Event。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            current_time = normalize_timestamp(self._clock())
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise InvalidPortfolioValue("Cash Event occurred_at 不得晚于当前时间")

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            rebuild_portfolio(user, transactions, cash_events)
            cash_event = CashEvent.create(
                user_id=user.id,
                sequence=len(cash_events) + 1,
                event_type=command.event_type,
                amount=command.amount,
                occurred_at=occurred_at,
                reason=command.reason,
            )
            ordered_cash_events = resequence_cash_events([*cash_events, cash_event])
            portfolio = rebuild_portfolio(user, transactions, ordered_cash_events)
            persisted_cash_event = next(
                candidate for candidate in ordered_cash_events if candidate.id == cash_event.id
            )
            persisted_by_id = {candidate.id: candidate for candidate in cash_events}
            existing_cash_events = [
                candidate for candidate in ordered_cash_events if candidate.id != cash_event.id
            ]
            if any(
                candidate.sequence != persisted_by_id[candidate.id].sequence
                for candidate in existing_cash_events
            ):
                unit_of_work.synchronize_cash_event_sequences(existing_cash_events)
            unit_of_work.add_cash_event(persisted_cash_event)
            unit_of_work.commit()
            return CashAdjustmentResult(
                cash_event=persisted_cash_event,
                portfolio=portfolio,
            )

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        """从持久化 Ledger 恢复当前 Portfolio State。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            return rebuild_portfolio(user, transactions, cash_events)

    def get_investment_context(self, user_id: UUID) -> InvestmentPortfolioContext:
        """用同一批 Ledger Facts 构造 Agent 所需 Portfolio Context。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            portfolio = rebuild_portfolio(user, transactions, cash_events)
            return InvestmentPortfolioContext.from_ledger(portfolio, tuple(transactions))

    def list_transactions(self, user_id: UUID) -> tuple[Transaction, ...]:
        """按 Ledger sequence 返回可追溯 Transaction。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_transactions(user.id))

    def list_cash_events(self, user_id: UUID) -> tuple[CashEvent, ...]:
        """按独立 Ledger sequence 返回可追溯 Cash Events。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_cash_events(user.id))
