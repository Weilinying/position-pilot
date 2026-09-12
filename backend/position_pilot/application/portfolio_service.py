"""Portfolio Application Service。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from position_pilot.application.errors import OpeningStateSealed, UserNotFound
from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.domain.errors import FutureTimestamp, InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    BuyTransactionCorrection,
    CashEvent,
    CashEventType,
    LotAllocation,
    LotClassificationChange,
    OpeningPosition,
    PortfolioState,
    PositionLotSource,
    PositionReconciliation,
    PositionType,
    ReplayResult,
    Transaction,
    TransactionAction,
    User,
    apply_buy_transaction_corrections,
    normalize_timestamp,
    rebuild_portfolio,
    replay_portfolio,
    resequence_cash_events,
    resequence_transactions,
)
from position_pilot.domain.portfolio_accounting import (
    PortfolioAccounting,
    calculate_portfolio_accounting,
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

    def list_opening_positions(self, user_id: UUID) -> list[OpeningPosition]: ...

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None: ...

    def list_position_reconciliations(self, user_id: UUID) -> list[PositionReconciliation]: ...

    def add_position_reconciliation(self, reconciliation: PositionReconciliation) -> None: ...

    def list_lot_allocations(self, user_id: UUID) -> list[LotAllocation]: ...

    def add_lot_allocations(self, allocations: list[LotAllocation]) -> None: ...

    def list_lot_classification_changes(
        self,
        user_id: UUID,
    ) -> list[LotClassificationChange]: ...

    def add_lot_classification_change(self, change: LotClassificationChange) -> None: ...

    def list_buy_transaction_corrections(
        self,
        user_id: UUID,
    ) -> list[BuyTransactionCorrection]: ...

    def add_buy_transaction_correction(self, correction: BuyTransactionCorrection) -> None: ...

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
    """追加交易的输入；BUY 价格含费，SELL fee 为实际费用。"""

    user_id: UUID
    ticker: str
    action: TransactionAction
    price: Decimal
    shares: Decimal
    fee: Decimal = Decimal("0")
    position_type: PositionType | None = None
    occurred_at: datetime | None = None
    reason: str | None = None
    allocations: tuple["LotAllocationInput", ...] = ()


@dataclass(frozen=True, slots=True)
class LotAllocationInput:
    """一笔 SELL 对一个当前批次的股数分配输入。"""

    lot_id: UUID
    shares: Decimal


@dataclass(frozen=True, slots=True)
class ChangeLotClassificationCommand:
    """调整整个剩余批次策略类型的输入。"""

    user_id: UUID
    lot_id: UUID
    position_type: PositionType


@dataclass(frozen=True, slots=True)
class LotClassificationResult:
    """批次类型变更及其最新 Portfolio。"""

    change: LotClassificationChange
    portfolio: PortfolioState


@dataclass(frozen=True, slots=True)
class CorrectBuyTransactionCommand:
    """用新版本成交字段更正一笔原始 BUY。"""

    user_id: UUID
    transaction_id: UUID
    price: Decimal
    shares: Decimal
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BuyTransactionCorrectionResult:
    """BUY 更正记录及其最新 Portfolio。"""

    correction: BuyTransactionCorrection
    portfolio: PortfolioState


@dataclass(frozen=True, slots=True)
class RecordCashEventCommand:
    """追加 Cash Event Ledger Record 的显式输入。"""

    user_id: UUID
    event_type: CashEventType
    amount: Decimal
    occurred_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class OpeningPositionInput:
    """一次 Opening State 初始化中的单行持仓输入。"""

    ticker: str
    shares: Decimal
    average_cost: Decimal
    position_type: PositionType | None = None


@dataclass(frozen=True, slots=True)
class InitializeOpeningPositionsCommand:
    """原子初始化 Existing Positions 的输入。"""

    user_id: UUID
    positions: tuple[OpeningPositionInput, ...]


@dataclass(frozen=True, slots=True)
class PositionReconciliationInput:
    """一次 Screenshot Reconciliation 中的单行目标持仓。"""

    ticker: str
    target_shares: Decimal
    target_average_cost: Decimal
    position_type: PositionType | None = None


@dataclass(frozen=True, slots=True)
class RecordPositionReconciliationsCommand:
    """原子追加同一份已确认截图中的全部持仓校准事实。"""

    user_id: UUID
    positions: tuple[PositionReconciliationInput, ...]
    source: str
    broker: str | None = None
    source_info: str | None = None


@dataclass(frozen=True, slots=True)
class CashAdjustmentResult:
    """同一事务内产生的 Cash Event 与重建后 Portfolio。"""

    cash_event: CashEvent
    portfolio: PortfolioState


@dataclass(frozen=True, slots=True)
class PositionReconciliationsResult:
    """同一事务内追加的全部校准事件与重建后 Portfolio。"""

    reconciliations: tuple[PositionReconciliation, ...]
    portfolio: PortfolioState


@dataclass(frozen=True, slots=True)
class PortfolioReplaySnapshot:
    """一次完整事实读取产生的 Replay 与有效交易视图。"""

    replay: ReplayResult
    effective_transactions: tuple[Transaction, ...]


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
                raise FutureTimestamp("Transaction occurred_at 不得晚于当前时间")

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            # 重新派生顺序前先验证已持久化 Ledger，避免意外掩盖 sequence 损坏。
            current_portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            transaction = Transaction.create(
                user_id=user.id,
                sequence=len(transactions) + 1,
                ticker=command.ticker,
                action=command.action,
                price=command.price,
                shares=command.shares,
                fee=command.fee,
                position_type=command.position_type,
                occurred_at=occurred_at,
                reason=command.reason,
            )

            if transaction.action is TransactionAction.BUY and command.allocations:
                raise InvalidPortfolioValue("BUY 不能包含卖出批次分配")
            if transaction.action is TransactionAction.SELL and not command.allocations:
                raise InvalidPortfolioValue("SELL 必须选择卖出的持仓批次")
            allocation_lot_ids = [item.lot_id for item in command.allocations]
            if len(allocation_lot_ids) != len(set(allocation_lot_ids)):
                raise InvalidPortfolioValue("SELL 不能重复分配同一批次")
            current_lots = {lot.id: lot for lot in current_portfolio.lots}
            new_allocations = [
                LotAllocation.create(
                    user_id=user.id,
                    sell_transaction_id=transaction.id,
                    lot_id=item.lot_id,
                    shares=item.shares,
                )
                for item in command.allocations
            ]
            if transaction.action is TransactionAction.SELL:
                if (
                    sum(
                        (allocation.shares for allocation in new_allocations),
                        Decimal("0"),
                    )
                    != transaction.shares
                ):
                    raise InvalidPortfolioValue("SELL 的批次分配合计必须等于成交股数")
                for allocation in new_allocations:
                    lot = current_lots.get(allocation.lot_id)
                    if lot is None or lot.ticker != transaction.ticker:
                        raise InvalidPortfolioValue("SELL 只能分配当前 ticker 的持仓批次")

            # sequence 是经济顺序的只读投影；历史补录会移动其后的派生序号。
            ordered_transactions = resequence_transactions([*transactions, transaction])
            current_portfolio = rebuild_portfolio(
                user,
                ordered_transactions,
                cash_events,
                opening_positions,
                reconciliations,
                [*lot_allocations, *new_allocations],
                classification_changes,
                buy_corrections,
            )
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
            unit_of_work.add_lot_allocations(new_allocations)
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
                raise FutureTimestamp("Cash Event occurred_at 不得晚于当前时间")

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            cash_event = CashEvent.create(
                user_id=user.id,
                sequence=len(cash_events) + 1,
                event_type=command.event_type,
                amount=command.amount,
                occurred_at=occurred_at,
                reason=command.reason,
            )
            ordered_cash_events = resequence_cash_events([*cash_events, cash_event])
            portfolio = rebuild_portfolio(
                user,
                transactions,
                ordered_cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
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

    def record_position_reconciliations(
        self,
        command: RecordPositionReconciliationsCommand,
        *,
        confirmed_at: datetime | None = None,
    ) -> PositionReconciliationsResult:
        """锁定 User，并原子追加一份截图或手工确认的汇总持仓校准事实。"""

        if not 1 <= len(command.positions) <= 100:
            raise InvalidPortfolioValue("positions 数量必须在 1 到 100 之间")

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            current_time = normalize_timestamp(self._clock())
            normalized_confirmed_at = normalize_timestamp(confirmed_at or current_time)
            if normalized_confirmed_at > current_time:
                raise FutureTimestamp("Position Reconciliation confirmed_at 不得晚于当前时间")

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            current_portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            new_reconciliations = [
                PositionReconciliation.create(
                    user_id=user.id,
                    ticker=item.ticker,
                    target_shares=item.target_shares,
                    target_average_cost=item.target_average_cost,
                    position_type=item.position_type,
                    source=command.source,
                    confirmed_at=normalized_confirmed_at,
                    broker=command.broker,
                    source_info=command.source_info,
                )
                for item in command.positions
            ]
            keys = {
                (reconciliation.ticker, reconciliation.position_type)
                for reconciliation in new_reconciliations
            }
            if len(keys) != len(new_reconciliations):
                raise InvalidPortfolioValue("positions 不能包含重复的 ticker 与 position_type")
            for ticker, position_type in keys:
                current_lots = [
                    lot
                    for lot in current_portfolio.lots
                    if lot.ticker == ticker and lot.position_type is position_type
                ]
                if len(current_lots) > 1 or any(
                    lot.source is PositionLotSource.BUY for lot in current_lots
                ):
                    raise InvalidPortfolioValue(
                        "存在详细购买批次，请通过购买批次更正或交易录入修改"
                    )
            portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                [*reconciliations, *new_reconciliations],
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            for reconciliation in new_reconciliations:
                unit_of_work.add_position_reconciliation(reconciliation)
            unit_of_work.commit()
            return PositionReconciliationsResult(
                reconciliations=tuple(new_reconciliations),
                portfolio=portfolio,
            )

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        """从持久化 Ledger 恢复当前 Portfolio State。"""

        return self.get_replay(user_id).portfolio

    def get_accounting(self, user_id: UUID) -> PortfolioAccounting:
        """只根据账本计算已实现收益，不读取行情。"""

        return calculate_portfolio_accounting(self.get_replay(user_id))

    def get_replay(self, user_id: UUID) -> ReplayResult:
        """读取同一批完整事实，共享一次持仓与卖出分配重放。"""

        return self.get_replay_snapshot(user_id).replay

    def get_replay_snapshot(self, user_id: UUID) -> PortfolioReplaySnapshot:
        """一次读取完整账本，返回重放结果及更正后的有效交易。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            return PortfolioReplaySnapshot(
                replay=replay_portfolio(
                    user,
                    transactions,
                    cash_events,
                    opening_positions,
                    reconciliations,
                    lot_allocations,
                    classification_changes,
                    buy_corrections,
                ),
                effective_transactions=tuple(
                    apply_buy_transaction_corrections(
                        user,
                        transactions,
                        buy_corrections,
                    )
                ),
            )

    def get_investment_context(self, user_id: UUID) -> InvestmentPortfolioContext:
        """用同一批 Ledger Facts 构造 Agent 所需 Portfolio Context。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            effective_transactions = apply_buy_transaction_corrections(
                user,
                transactions,
                buy_corrections,
            )
            return InvestmentPortfolioContext.from_ledger(
                portfolio,
                tuple(effective_transactions),
            )

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        """在首个经济 Mutation 前原子写入一次 Opening State。"""

        if not 1 <= len(command.positions) <= 100:
            raise InvalidPortfolioValue("positions 数量必须在 1 到 100 之间")

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            existing_opening_positions = unit_of_work.list_opening_positions(user.id)
            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            if (
                existing_opening_positions
                or transactions
                or cash_events
                or reconciliations
                or lot_allocations
                or classification_changes
                or buy_corrections
            ):
                raise OpeningStateSealed()

            recorded_at = normalize_timestamp(self._clock())
            opening_positions = [
                OpeningPosition.create(
                    user_id=user.id,
                    ticker=item.ticker,
                    shares=item.shares,
                    average_cost=item.average_cost,
                    position_type=item.position_type,
                    recorded_at=recorded_at,
                )
                for item in command.positions
            ]
            keys = {(position.ticker, position.position_type) for position in opening_positions}
            if len(keys) != len(opening_positions):
                raise InvalidPortfolioValue("positions 不能包含重复的 ticker 与 position_type")

            rebuild_portfolio(user, [], [], opening_positions, [])
            ordered = sorted(
                opening_positions,
                key=lambda position: (position.ticker, position.position_type.value),
            )
            unit_of_work.add_opening_positions(ordered)
            unit_of_work.commit()
            return tuple(ordered)

    def list_opening_positions(self, user_id: UUID) -> tuple[OpeningPosition, ...]:
        """按稳定 Position Key 返回完整 Opening State。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_opening_positions(user.id))

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

    def list_position_reconciliations(
        self,
        user_id: UUID,
    ) -> tuple[PositionReconciliation, ...]:
        """按确认时间返回完整的不可变持仓校准事实。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_position_reconciliations(user.id))

    def list_buy_transaction_corrections(
        self,
        user_id: UUID,
    ) -> tuple[BuyTransactionCorrection, ...]:
        """按更正时间返回完整 BUY 更正记录。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(user_id)
            if user is None:
                raise UserNotFound(user_id)
            return tuple(unit_of_work.list_buy_transaction_corrections(user.id))

    def change_lot_classification(
        self,
        command: ChangeLotClassificationCommand,
    ) -> LotClassificationResult:
        """把一个当前剩余批次整体调整为新的策略类型。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            transactions = unit_of_work.list_transactions(user.id)
            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            lot = next((item for item in portfolio.lots if item.id == command.lot_id), None)
            if lot is None:
                raise InvalidPortfolioValue("只能修改当前仍有持仓的批次")
            if lot.position_type is command.position_type:
                raise InvalidPortfolioValue("批次已经属于该持仓类型")

            change = LotClassificationChange.create(
                user_id=user.id,
                lot_id=lot.id,
                position_type=command.position_type,
                effective_at=normalize_timestamp(self._clock()),
            )
            updated_portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                [*classification_changes, change],
                buy_corrections,
            )
            unit_of_work.add_lot_classification_change(change)
            unit_of_work.commit()
            return LotClassificationResult(change=change, portfolio=updated_portfolio)

    def correct_buy_transaction(
        self,
        command: CorrectBuyTransactionCommand,
    ) -> BuyTransactionCorrectionResult:
        """保留原 BUY，并追加一版可重放的有效成交字段。"""

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.get_user(command.user_id, for_update=True)
            if user is None:
                raise UserNotFound(command.user_id)

            current_time = normalize_timestamp(self._clock())
            occurred_at = normalize_timestamp(command.occurred_at)
            if occurred_at > current_time:
                raise FutureTimestamp("BUY Correction occurred_at 不得晚于当前时间")
            transactions = unit_of_work.list_transactions(user.id)
            original = next(
                (item for item in transactions if item.id == command.transaction_id),
                None,
            )
            if original is None or original.action is not TransactionAction.BUY:
                raise InvalidPortfolioValue("只能更正当前 BUY 批次的原始交易")

            cash_events = unit_of_work.list_cash_events(user.id)
            opening_positions = unit_of_work.list_opening_positions(user.id)
            reconciliations = unit_of_work.list_position_reconciliations(user.id)
            lot_allocations = unit_of_work.list_lot_allocations(user.id)
            classification_changes = unit_of_work.list_lot_classification_changes(user.id)
            buy_corrections = unit_of_work.list_buy_transaction_corrections(user.id)
            current_portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                buy_corrections,
            )
            if not any(lot.id == original.id for lot in current_portfolio.lots):
                raise InvalidPortfolioValue("只能更正当前仍有持仓的 BUY 批次")

            correction = BuyTransactionCorrection.create(
                user_id=user.id,
                transaction_id=original.id,
                price=command.price,
                shares=command.shares,
                occurred_at=occurred_at,
                reason=command.reason,
                corrected_at=current_time,
            )
            portfolio = rebuild_portfolio(
                user,
                transactions,
                cash_events,
                opening_positions,
                reconciliations,
                lot_allocations,
                classification_changes,
                [*buy_corrections, correction],
            )
            unit_of_work.add_buy_transaction_correction(correction)
            unit_of_work.commit()
            return BuyTransactionCorrectionResult(correction=correction, portfolio=portfolio)
