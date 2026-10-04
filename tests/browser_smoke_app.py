"""M8 Engineering Browser Smoke 使用的确定性本地应用替身。

该模块只用于人工检查和定向 Engineering Smoke。它替换真实数据库与真实
Investment Agent，不是生产入口、不是自动化 E2E，也不构成真实模型验收证据。
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import RLock
from time import sleep
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

from fastapi import Request
from starlette.responses import RedirectResponse, Response

from position_pilot.api.routers.conversation import (
    get_conversation_auth_service_dependency,
    get_conversation_service_dependency,
)
from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.auth_service import Account, AuthService, AuthSession
from position_pilot.application.conversation_service import (
    ConversationAgentResult,
    ConversationHistoryMessage,
    ConversationMessage,
    ConversationMessagePage,
    ConversationMessageRole,
    ConversationService,
    ConversationSource,
    ConversationSourceInput,
    ConversationThread,
    ConversationThreadPage,
    ConversationTurn,
    ConversationTurnStatus,
)
from position_pilot.application.errors import OpeningStateSealed, UserNotFound
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.opening_import_service import OpeningImportService
from position_pilot.application.portfolio_chart_service import PortfolioChartService
from position_pilot.application.portfolio_service import (
    BuyTransactionCorrectionResult,
    CashAdjustmentResult,
    ChangeLotClassificationCommand,
    CorrectBuyTransactionCommand,
    CreateUserCommand,
    InitializeOpeningPositionsCommand,
    LotClassificationResult,
    PortfolioReplaySnapshot,
    PositionReconciliationsResult,
    RecordCashEventCommand,
    RecordPositionReconciliationsCommand,
    RecordTransactionCommand,
)
from position_pilot.application.portfolio_summary_service import PortfolioSummaryService
from position_pilot.application.portfolio_valuation_service import PortfolioValuationService
from position_pilot.application.recognition_service import (
    DraftField,
    RecognitionDraft,
    RecognitionDraftRow,
    RecognitionFieldStatus,
    RecognitionInput,
    RecognitionInputKind,
    RecognitionProvider,
    RecognitionResult,
    RecognitionService,
)
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetValidationQuery,
    AssetValidationResult,
)
from position_pilot.domain.errors import FutureTimestamp
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketQuote,
    OHLCVBar,
)
from position_pilot.domain.portfolio import (
    BuyTransactionCorrection,
    CashBalance,
    CashEvent,
    LotAllocation,
    LotClassificationChange,
    OpeningPosition,
    PortfolioState,
    Position,
    PositionLot,
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
from position_pilot.main import (
    app,
    get_asset_metadata_service_dependency,
    get_auth_service_dependency,
    get_investment_agent_dependency,
    get_opening_import_service_dependency,
    get_portfolio_chart_service_dependency,
    get_portfolio_service_dependency,
    get_portfolio_summary_service_dependency,
    get_portfolio_valuation_service_dependency,
    get_recognition_service_dependency,
)

USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
SLOW_USER = UUID("30000000-0000-4000-8000-000000000003")
EMPTY_USER = UUID("40000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
BROWSER_SMOKE_IS_ENGINEERING_FIXTURE = True
BROWSER_SMOKE_AGENT_NOTICE = (
    "Engineering smoke only: BrowserSmokeInvestmentAgent is deterministic and fake; "
    "it is not the real Investment Agent or real market data."
)


@app.middleware("http")
async def show_engineering_smoke_notice(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """强制工程替身页面显示 Fake Agent 与固定数据警告。"""

    if request.url.path.rstrip("/") == "/app" and "engineering_smoke" not in request.query_params:
        return RedirectResponse("/app/?engineering_smoke=1", status_code=307)
    return await call_next(request)


def _portfolio(user_id: UUID, *, ticker: str) -> PortfolioState:
    """创建包含双 Position Type 的稳定 Browser Fixture。"""

    return PortfolioState(
        user_id=user_id,
        cash=CashBalance(
            user_id=user_id,
            initial_cash=Decimal("10000.00000000"),
            available_cash=Decimal("5120.50000000"),
        ),
        positions=(
            Position(
                ticker=ticker,
                position_type=PositionType.LONG_TERM,
                shares=Decimal("10.00000000"),
                average_cost=Decimal("180.03500000"),
                cost_basis=Decimal("1800.35000000"),
            ),
            Position(
                ticker=ticker,
                position_type=PositionType.SWING,
                shares=Decimal("4.00000000"),
                average_cost=Decimal("210.08750000"),
                cost_basis=Decimal("840.35000000"),
            ),
        ),
        transaction_count=2,
        lots=(
            PositionLot(
                id=UUID(f"{user_id.hex[:24]}00000001"),
                ticker=ticker,
                position_type=PositionType.LONG_TERM,
                source=PositionLotSource.BUY,
                acquired_shares=Decimal("10.00000000"),
                remaining_shares=Decimal("10.00000000"),
                average_cost=Decimal("180.03500000"),
                cost_basis=Decimal("1800.35000000"),
                entry_price=Decimal("180.00000000"),
                purchased_at=NOW,
            ),
            PositionLot(
                id=UUID(f"{user_id.hex[:24]}00000002"),
                ticker=ticker,
                position_type=PositionType.SWING,
                source=PositionLotSource.BUY,
                acquired_shares=Decimal("4.00000000"),
                remaining_shares=Decimal("4.00000000"),
                average_cost=Decimal("210.08750000"),
                cost_basis=Decimal("840.35000000"),
                entry_price=Decimal("210.00000000"),
                purchased_at=NOW,
            ),
        ),
    )


class BrowserSmokePortfolioService:
    """提供固定读取 Fixture 与可写的进程内 Portfolio。"""

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._transactions: dict[UUID, list[Transaction]] = {}
        self._cash_events: dict[UUID, list[CashEvent]] = {}
        self._opening_positions: dict[UUID, list[OpeningPosition]] = {}
        self._reconciliations: dict[UUID, list[PositionReconciliation]] = {}
        self._lot_allocations: dict[UUID, list[LotAllocation]] = {}
        self._classification_changes: dict[UUID, list[LotClassificationChange]] = {}
        self._buy_corrections: dict[UUID, list[BuyTransactionCorrection]] = {}
        self._lock = RLock()

    def create_user(self, command: CreateUserCommand) -> User:
        """创建隔离的 Engineering Smoke User。"""

        with self._lock:
            user = User.create(
                display_name=command.display_name,
                initial_cash=command.initial_cash,
            )
            self._users[user.id] = user
            self._transactions[user.id] = []
            self._cash_events[user.id] = []
            self._opening_positions[user.id] = []
            self._reconciliations[user.id] = []
            self._lot_allocations[user.id] = []
            self._classification_changes[user.id] = []
            self._buy_corrections[user.id] = []
            return user

    def add_auth_user(self, user: User) -> None:
        """把 Auth Service 创建的 User 接入同一个 Engineering Smoke Portfolio Store。"""

        with self._lock:
            self._users[user.id] = user
            self._transactions[user.id] = []
            self._cash_events[user.id] = []
            self._opening_positions[user.id] = []
            self._reconciliations[user.id] = []
            self._lot_allocations[user.id] = []
            self._classification_changes[user.id] = []
            self._buy_corrections[user.id] = []

    def add_auth_opening_positions(self, opening_positions: list[OpeningPosition]) -> None:
        """保存 Auth Portfolio Setup 已验证的 Opening Positions。"""

        with self._lock:
            for position in opening_positions:
                if position.user_id not in self._users:
                    raise UserNotFound(position.user_id)
                self._opening_positions[position.user_id].append(position)

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        """在首个经济记录前原子保存 Engineering Smoke 期初仓位。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            if (
                self._opening_positions[user.id]
                or self._transactions[user.id]
                or self._cash_events[user.id]
                or self._reconciliations[user.id]
            ):
                raise OpeningStateSealed()
            recorded_at = datetime.now(UTC)
            positions = [
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
            rebuild_portfolio(user, [], [], positions, [])
            self._opening_positions[user.id] = positions
            return tuple(
                sorted(positions, key=lambda item: (item.ticker, item.position_type.value))
            )

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction:
        """使用正式 Domain 规则追加 Engineering Smoke Transaction。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            transactions = self._transactions[user.id]
            cash_events = self._cash_events[user.id]
            current_time = datetime.now(UTC)
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise FutureTimestamp("Transaction occurred_at 不得晚于当前时间")
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
            new_allocations = [
                LotAllocation.create(
                    user_id=user.id,
                    sell_transaction_id=transaction.id,
                    lot_id=item.lot_id,
                    shares=item.shares,
                )
                for item in command.allocations
            ]
            if transaction.action is TransactionAction.SELL and not new_allocations:
                raise ValueError("SELL 必须选择批次")
            ordered = resequence_transactions([*transactions, transaction])
            rebuild_portfolio(
                user,
                ordered,
                cash_events,
                self._opening_positions[user.id],
                self._reconciliations[user.id],
                [*self._lot_allocations[user.id], *new_allocations],
                self._classification_changes[user.id],
                self._buy_corrections[user.id],
            )
            self._transactions[user.id] = ordered
            self._lot_allocations[user.id].extend(new_allocations)
            return next(candidate for candidate in ordered if candidate.id == transaction.id)

    def record_cash_event(self, command: RecordCashEventCommand) -> CashAdjustmentResult:
        """使用正式 Domain 规则追加 Engineering Smoke Cash Event。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            transactions = self._transactions[user.id]
            cash_events = self._cash_events[user.id]
            current_time = datetime.now(UTC)
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise FutureTimestamp("Cash Event occurred_at 不得晚于当前时间")
            cash_event = CashEvent.create(
                user_id=user.id,
                sequence=len(cash_events) + 1,
                event_type=command.event_type,
                amount=command.amount,
                occurred_at=occurred_at,
                reason=command.reason,
            )
            ordered = resequence_cash_events([*cash_events, cash_event])
            portfolio = rebuild_portfolio(
                user,
                transactions,
                ordered,
                self._opening_positions[user.id],
                self._reconciliations[user.id],
                self._lot_allocations[user.id],
                self._classification_changes[user.id],
                self._buy_corrections[user.id],
            )
            self._cash_events[user.id] = ordered
            persisted = next(candidate for candidate in ordered if candidate.id == cash_event.id)
            return CashAdjustmentResult(cash_event=persisted, portfolio=portfolio)

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        with self._lock:
            user = self._users.get(user_id)
            if user is not None:
                return rebuild_portfolio(
                    user,
                    self._transactions[user_id],
                    self._cash_events[user_id],
                    self._opening_positions[user_id],
                    self._reconciliations[user_id],
                    self._lot_allocations[user_id],
                    self._classification_changes[user_id],
                    self._buy_corrections[user_id],
                )
        if user_id == EMPTY_USER:
            return PortfolioState(
                user_id=user_id,
                cash=CashBalance(
                    user_id=user_id,
                    initial_cash=Decimal("10000.00000000"),
                    available_cash=Decimal("10000.00000000"),
                ),
                positions=(),
                transaction_count=0,
            )
        if user_id == SLOW_USER:
            sleep(0.6)
            return _portfolio(user_id, ticker="SLOW")
        if user_id == USER_A:
            return _portfolio(user_id, ticker="GOOG")
        if user_id == USER_B:
            return _portfolio(user_id, ticker="NVDA")
        raise UserNotFound(user_id)

    def list_opening_positions(self, user_id: UUID) -> tuple[OpeningPosition, ...]:
        """返回 Engineering Smoke 的完整期初仓位列表。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._opening_positions[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER}:
            ticker = {USER_A: "GOOG", USER_B: "NVDA", SLOW_USER: "SLOW"}[user_id]
            return (
                OpeningPosition.create(
                    user_id=user_id,
                    ticker=ticker,
                    shares=Decimal("10"),
                    average_cost=Decimal("180.035"),
                    position_type=PositionType.LONG_TERM,
                    recorded_at=NOW,
                ),
                OpeningPosition.create(
                    user_id=user_id,
                    ticker=ticker,
                    shares=Decimal("4"),
                    average_cost=Decimal("210.0875"),
                    position_type=PositionType.SWING,
                    recorded_at=NOW,
                ),
            )
        if user_id == EMPTY_USER:
            return ()
        raise UserNotFound(user_id)

    def list_transactions(self, user_id: UUID) -> tuple[Transaction, ...]:
        """返回 Engineering Smoke 的完整交易列表。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._transactions[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER, EMPTY_USER}:
            return ()
        raise UserNotFound(user_id)

    def get_replay(self, user_id: UUID) -> ReplayResult:
        """按真实 Replay 生成当前持仓与收益明细，供 M11 首页聚合读取。"""

        with self._lock:
            user = self._users.get(user_id)
            if user is not None:
                return replay_portfolio(
                    user,
                    self._transactions[user_id],
                    self._cash_events[user_id],
                    self._opening_positions[user_id],
                    self._reconciliations[user_id],
                    self._lot_allocations[user_id],
                    self._classification_changes[user_id],
                    self._buy_corrections[user_id],
                )
        if user_id == EMPTY_USER:
            return ReplayResult(portfolio=self.get_portfolio(user_id), sell_allocation_results=())
        if user_id in {USER_A, USER_B, SLOW_USER}:
            ticker = {USER_A: "GOOG", USER_B: "NVDA", SLOW_USER: "SLOW"}[user_id]
            if user_id == SLOW_USER:
                sleep(0.6)
            return ReplayResult(
                portfolio=_portfolio(user_id, ticker=ticker),
                sell_allocation_results=(),
            )
        raise UserNotFound(user_id)

    def get_replay_snapshot(self, user_id: UUID) -> PortfolioReplaySnapshot:
        """返回 Chart Service 所需的 Replay 与有效交易快照。"""

        with self._lock:
            user = self._users.get(user_id)
            if user is not None:
                transactions = self._transactions[user_id]
                corrections = self._buy_corrections[user_id]
                return PortfolioReplaySnapshot(
                    replay=replay_portfolio(
                        user,
                        transactions,
                        self._cash_events[user_id],
                        self._opening_positions[user_id],
                        self._reconciliations[user_id],
                        self._lot_allocations[user_id],
                        self._classification_changes[user_id],
                        corrections,
                    ),
                    effective_transactions=tuple(
                        apply_buy_transaction_corrections(user, transactions, corrections)
                    ),
                )
        if user_id == EMPTY_USER:
            return PortfolioReplaySnapshot(
                replay=ReplayResult(
                    portfolio=self.get_portfolio(user_id), sell_allocation_results=()
                ),
                effective_transactions=(),
            )
        if user_id in {USER_A, USER_B, SLOW_USER}:
            ticker = {USER_A: "GOOG", USER_B: "NVDA", SLOW_USER: "SLOW"}[user_id]
            if user_id == SLOW_USER:
                sleep(0.6)
            return PortfolioReplaySnapshot(
                replay=ReplayResult(
                    portfolio=_portfolio(user_id, ticker=ticker),
                    sell_allocation_results=(),
                ),
                effective_transactions=(),
            )
        raise UserNotFound(user_id)

    def get_accounting(self, user_id: UUID) -> PortfolioAccounting:
        """返回真实 Replay 产生的已实现收益核算，供只读会计接口使用。"""

        return calculate_portfolio_accounting(self.get_replay(user_id))

    def record_position_reconciliations(
        self,
        command: RecordPositionReconciliationsCommand,
    ) -> PositionReconciliationsResult:
        """追加 Engineering Smoke 使用的不可变持仓校准事实。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            confirmed_at = datetime.now(UTC)
            reconciliations = tuple(
                PositionReconciliation.create(
                    user_id=user.id,
                    ticker=item.ticker,
                    target_shares=item.target_shares,
                    target_average_cost=item.target_average_cost,
                    position_type=item.position_type,
                    source=command.source,
                    confirmed_at=confirmed_at,
                    broker=command.broker,
                    source_info=command.source_info,
                )
                for item in command.positions
            )
            self._reconciliations[user.id].extend(reconciliations)
            portfolio = rebuild_portfolio(
                user,
                self._transactions[user.id],
                self._cash_events[user.id],
                self._opening_positions[user.id],
                self._reconciliations[user.id],
                self._lot_allocations[user.id],
                self._classification_changes[user.id],
                self._buy_corrections[user.id],
            )
            return PositionReconciliationsResult(reconciliations, portfolio)

    def change_lot_classification(
        self,
        command: ChangeLotClassificationCommand,
    ) -> LotClassificationResult:
        """记录批次类型变更并重建 Engineering Smoke Portfolio。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            change = LotClassificationChange.create(
                user_id=user.id,
                lot_id=command.lot_id,
                position_type=command.position_type,
                effective_at=datetime.now(UTC),
            )
            self._classification_changes[user.id].append(change)
            portfolio = self.get_portfolio(user.id)
            return LotClassificationResult(change, portfolio)

    def correct_buy_transaction(
        self,
        command: CorrectBuyTransactionCommand,
    ) -> BuyTransactionCorrectionResult:
        """记录 BUY 更正并重建 Engineering Smoke Portfolio。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            correction = BuyTransactionCorrection.create(
                user_id=user.id,
                transaction_id=command.transaction_id,
                price=command.price,
                shares=command.shares,
                occurred_at=command.occurred_at,
                reason=command.reason,
                corrected_at=datetime.now(UTC),
            )
            self._buy_corrections[user.id].append(correction)
            portfolio = self.get_portfolio(user.id)
            return BuyTransactionCorrectionResult(correction, portfolio)

    def list_buy_transaction_corrections(
        self,
        user_id: UUID,
    ) -> tuple[BuyTransactionCorrection, ...]:
        """返回 Engineering Smoke 的 BUY 更正。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._buy_corrections[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER, EMPTY_USER}:
            return ()
        raise UserNotFound(user_id)

    def list_position_reconciliations(
        self,
        user_id: UUID,
    ) -> tuple[PositionReconciliation, ...]:
        """返回 Engineering Smoke 的完整持仓校准事实。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._reconciliations[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER, EMPTY_USER}:
            return ()
        raise UserNotFound(user_id)

    def list_cash_events(self, user_id: UUID) -> tuple[CashEvent, ...]:
        """返回 Engineering Smoke 的完整现金事件列表。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._cash_events[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER, EMPTY_USER}:
            return ()
        raise UserNotFound(user_id)

    def _require_mutable_user(self, user_id: UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise UserNotFound(user_id)
        return user


@dataclass(slots=True)
class BrowserSmokeAuthStore:
    """Engineering Smoke 所需的进程内 Account 与 Session 状态。"""

    accounts_by_id: dict[UUID, Account] = field(default_factory=dict)
    account_ids_by_email: dict[str, UUID] = field(default_factory=dict)
    sessions: dict[str, AuthSession] = field(default_factory=dict)


class BrowserSmokeAuthUnitOfWork:
    """把 Auth Service 的最小事务接口映射到进程内 Smoke Store。"""

    def __init__(
        self,
        store: BrowserSmokeAuthStore,
        portfolio_service: BrowserSmokePortfolioService,
    ) -> None:
        self.store = store
        self.portfolio_service = portfolio_service

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback

    def get_account_by_email(
        self,
        email: str,
        *,
        for_update: bool = False,
    ) -> Account | None:
        del for_update
        account_id = self.store.account_ids_by_email.get(email)
        return self.store.accounts_by_id.get(account_id) if account_id is not None else None

    def get_account_by_id(
        self,
        account_id: UUID,
        *,
        for_update: bool = False,
    ) -> Account | None:
        del for_update
        return self.store.accounts_by_id.get(account_id)

    def add_account(self, account: Account) -> None:
        self.store.accounts_by_id[account.id] = account
        self.store.account_ids_by_email[account.email] = account.id

    def set_account_portfolio(self, account_id: UUID, user_id: UUID) -> None:
        account = self.store.accounts_by_id[account_id]
        self.store.accounts_by_id[account_id] = replace(account, portfolio_user_id=user_id)

    def get_auth_session(self, token_digest: str) -> AuthSession | None:
        return self.store.sessions.get(token_digest)

    def add_auth_session(self, auth_session: AuthSession) -> None:
        self.store.sessions[auth_session.token_digest] = auth_session

    def delete_auth_session(self, token_digest: str) -> None:
        self.store.sessions.pop(token_digest, None)

    def add_user(self, user: User) -> None:
        self.portfolio_service.add_auth_user(user)

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None:
        self.portfolio_service.add_auth_opening_positions(opening_positions)

    def commit(self) -> None:
        """Smoke Store 没有外部事务，提交由调用完成即视为成功。"""


@dataclass(slots=True)
class BrowserSmokeConversationStore:
    """Engineering Smoke 使用的 Account-owned Conversation 内存 Store。

    该 Store 只覆盖 Browser Smoke 所需的最小生命周期；它不模拟 PostgreSQL
    事务、行锁、唯一索引或生产级恢复语义。正式 Persistence 行为仍由 T3/T4A
    的 PostgreSQL Integration Test 验证。
    """

    threads: dict[UUID, ConversationThread] = field(default_factory=dict)
    turns: dict[UUID, ConversationTurn] = field(default_factory=dict)
    messages: dict[UUID, ConversationMessage] = field(default_factory=dict)
    sources: dict[UUID, ConversationSource] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock, repr=False)


class BrowserSmokeConversationUnitOfWork:
    """把 Conversation Service 的最小 Port 映射到进程内 Smoke Store。"""

    def __init__(self, store: BrowserSmokeConversationStore) -> None:
        self.store = store

    def __enter__(self) -> Self:
        self.store.lock.acquire()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.store.lock.release()

    def get_thread(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThread | None:
        del for_update
        thread = self.store.threads.get(thread_id)
        return thread if thread is not None and thread.account_id == account_id else None

    def add_thread(self, thread: ConversationThread) -> None:
        self.store.threads[thread.id] = thread

    def update_thread(self, thread: ConversationThread) -> None:
        self.store.threads[thread.id] = thread

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> ConversationThreadPage:
        del cursor
        items = sorted(
            (
                thread
                for thread in self.store.threads.values()
                if thread.account_id == account_id and thread.deleted_at is None
            ),
            key=lambda thread: (thread.updated_at, thread.id),
            reverse=True,
        )
        return ConversationThreadPage(tuple(items[:limit]), None)

    def get_turn_by_client_request_id(
        self,
        account_id: UUID,
        thread_id: UUID,
        client_request_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        return next(
            (
                turn
                for turn in self.store.turns.values()
                if turn.account_id == account_id
                and turn.thread_id == thread_id
                and turn.client_request_id == client_request_id
            ),
            None,
        )

    def get_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        turn = self.store.turns.get(turn_id)
        return (
            turn
            if turn is not None and turn.account_id == account_id and turn.thread_id == thread_id
            else None
        )

    def get_running_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        return next(
            (
                turn
                for turn in self.store.turns.values()
                if turn.account_id == account_id
                and turn.thread_id == thread_id
                and turn.status is ConversationTurnStatus.RUNNING
            ),
            None,
        )

    def get_last_turn(self, account_id: UUID, thread_id: UUID) -> ConversationTurn | None:
        turns = [
            turn
            for turn in self.store.turns.values()
            if turn.account_id == account_id and turn.thread_id == thread_id
        ]
        return max(turns, key=lambda turn: (turn.created_at, turn.id), default=None)

    def get_user_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        return self._message_for_turn(
            account_id,
            thread_id,
            turn_id,
            ConversationMessageRole.USER,
        )

    def get_assistant_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        return self._message_for_turn(
            account_id,
            thread_id,
            turn_id,
            ConversationMessageRole.ASSISTANT,
        )

    def add_turn(self, turn: ConversationTurn) -> None:
        self.store.turns[turn.id] = turn

    def update_turn(self, turn: ConversationTurn) -> None:
        self.store.turns[turn.id] = turn

    def add_message(self, message: ConversationMessage) -> None:
        self.store.messages[message.id] = message

    def add_sources(self, sources: Sequence[ConversationSource]) -> None:
        self.store.sources.update({source.source_id: source for source in sources})

    def list_sources_for_message(
        self,
        account_id: UUID,
        thread_id: UUID,
        assistant_message_id: UUID,
    ) -> tuple[ConversationSource, ...]:
        message = self.store.messages.get(assistant_message_id)
        if (
            message is None
            or message.account_id != account_id
            or message.thread_id != thread_id
            or message.role is not ConversationMessageRole.ASSISTANT
        ):
            return ()
        return tuple(
            source
            for source in self.store.sources.values()
            if source.assistant_message_id == assistant_message_id
        )

    def list_messages(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None,
        limit: int,
    ) -> ConversationMessagePage:
        messages = [
            message
            for message in self.store.messages.values()
            if message.account_id == account_id
            and message.thread_id == thread_id
            and (before_sequence is None or message.sequence < before_sequence)
        ]
        ordered = sorted(messages, key=lambda message: message.sequence, reverse=True)
        has_next = len(ordered) > limit
        page = list(reversed(ordered[:limit]))
        next_cursor = str(page[0].sequence) if has_next and page else None
        return ConversationMessagePage(tuple(page), next_cursor)

    def commit(self) -> None:
        """Smoke Store 没有外部事务，调用完成即视为已提交。"""

    def _message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        role: ConversationMessageRole,
    ) -> ConversationMessage | None:
        return next(
            (
                message
                for message in self.store.messages.values()
                if message.account_id == account_id
                and message.thread_id == thread_id
                and message.turn_id == turn_id
                and message.role is role
            ),
            None,
        )


class BrowserSmokeConversationAgent:
    """返回固定 Citation 的 Conversation Fake Agent，不代表真实模型行为。"""

    def answer(
        self,
        *,
        account_id: UUID,
        portfolio_user_id: UUID,
        question: str,
        history: tuple[ConversationHistoryMessage, ...],
    ) -> ConversationAgentResult:
        del account_id, portfolio_user_id, question, history
        source_id = uuid4()
        return ConversationAgentResult(
            answer=(
                "这是本地 Engineering Smoke 的固定回答：已读取当前会话上下文与模拟报价。"
                f"该来源仅用于验证 Thread、History 与 Citation 展示 [source:{source_id}]"
            ),
            sources=(
                ConversationSourceInput(
                    source_id=source_id,
                    source_type="CURRENT_QUOTE",
                    provider="BROWSER_SMOKE",
                    provider_reference="GOOG:fixture-quote",
                    event_time=NOW,
                    fetched_at=NOW,
                    content_scope="STRUCTURED_FACT",
                    status="OK",
                ),
            ),
            warnings=("ENGINEERING_SMOKE_FAKE_AGENT",),
        )


class BrowserSmokeInvestmentAgent:
    """按问题文本返回固定结果的 Fake Agent，不代表真实模型行为。"""

    def answer(
        self,
        user_id: UUID,
        question: str,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        if question == "FAIL_503":
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                "Controlled provider failure",
            )
        if question == "FAIL_422":
            return InvestmentRequestFailure(
                InvestmentFailureCode.INVALID_QUESTION,
                "Controlled invalid question",
            )
        if question == "ERROR_XSS":
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                '<img src=x onerror="window.__xssExecuted=true">',
            )
        if question == "SLOW_A":
            sleep(0.6)
            return InvestmentAnswer(
                InvestmentResponseStatus.OK,
                f"Delayed answer for {user_id}",
                (ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),),
            )
        if question == "DEGRADED":
            return InvestmentAnswer(
                InvestmentResponseStatus.DEGRADED,
                "当前报价不可用；该回答只使用已加载持仓。",
                (
                    ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                    ContextSource(
                        ContextSourceType.CURRENT_QUOTE,
                        "NO_DATA",
                        ticker="GOOG",
                    ),
                    ContextSource(
                        ContextSourceType.RECENT_NEWS,
                        "PROVIDER_UNAVAILABLE",
                        ticker="GOOG",
                    ),
                ),
            )
        if question == "XSS":
            return InvestmentAnswer(
                InvestmentResponseStatus.OK,
                '<img src=x onerror="window.__xssExecuted=true">',
                (
                    ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                    ContextSource(
                        ContextSourceType.CURRENT_QUOTE,
                        "OK",
                        ticker="GOOG",
                        provider="<script>window.__xssExecuted=true</script>",
                        feed='<img src=x onerror="window.__xssExecuted=true">',
                        market_timestamp=NOW,
                        fetched_at=NOW,
                    ),
                ),
            )
        return InvestmentAnswer(
            InvestmentResponseStatus.OK,
            (
                "这是本地 Smoke 环境的示例回答：系统已读取当前投资组合，并成功取得 GOOG "
                "的模拟报价来源。该环境只验证问答与来源展示，不提供真实行情或模型分析，"
                "因此不能据此判断是否应该加仓。"
            ),
            (
                ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                ContextSource(
                    ContextSourceType.CURRENT_QUOTE,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    feed="IEX",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
            ),
        )


def _smoke_asset(symbol: str, display_name: str, exchange: str = "NASDAQ") -> AssetIdentity:
    """创建供 Import UI 使用的最小 Asset Fixture。"""

    return AssetIdentity(
        canonical_symbol=symbol,
        display_name=display_name,
        exchange=exchange,
    )


class BrowserSmokeAssetMetadataProvider:
    """提供不访问网络的 Asset Search / exact Validation Fixture。"""

    _assets = (
        _smoke_asset("ADBE", "Adobe Inc."),
        _smoke_asset("GOOG", "Alphabet Inc."),
        _smoke_asset("GOOGL", "Alphabet Inc."),
        _smoke_asset("NVDA", "NVIDIA Corporation"),
        _smoke_asset("SPY", "SPDR S&P 500 ETF Trust", "NYSE ARCA"),
    )

    def search(self, query: AssetSearchQuery) -> AssetSearchResult:
        """按 symbol 或公司名称返回固定 active 候选。"""

        normalized = query.query.casefold()
        candidates = tuple(
            asset
            for asset in self._assets
            if normalized in asset.canonical_symbol.casefold()
            or normalized in asset.display_name.casefold()
        )[: query.limit]
        if not candidates:
            return AssetSearchResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Smoke fixture 没有找到匹配 Asset",
            )
        return AssetSearchResult.success(candidates)

    def get_exact(self, query: AssetValidationQuery) -> AssetValidationResult:
        """对固定候选执行 deterministic exact Validation。"""

        for asset in self._assets:
            if asset.canonical_symbol == query.symbol:
                return AssetValidationResult.success(asset)
        return AssetValidationResult.failure(
            AssetMetadataStatus.NO_MATCH,
            "Smoke fixture 没有找到对应 Asset",
        )


def _smoke_draft_row(
    *,
    ticker: str | None,
    suggested_symbol: str | None,
    shares: str | None,
    average_cost: str | None,
    position_type: PositionType | None = None,
    confidence: str | None = "0.93",
    ticker_status: RecognitionFieldStatus | None = None,
    suggested_status: RecognitionFieldStatus | None = None,
) -> RecognitionDraftRow:
    """创建可供 Browser Smoke Review 的临时 Draft 行。"""

    def text_field(value: str | None, status: RecognitionFieldStatus | None) -> DraftField[str]:
        return DraftField(
            value=value,
            status=status
            or (
                RecognitionFieldStatus.PRESENT
                if value is not None
                else RecognitionFieldStatus.MISSING
            ),
        )

    def decimal_field(value: str | None) -> DraftField[Decimal]:
        return DraftField(
            value=Decimal(value) if value is not None else None,
            status=RecognitionFieldStatus.PRESENT
            if value is not None
            else RecognitionFieldStatus.MISSING,
        )

    return RecognitionDraftRow(
        ticker=text_field(ticker, ticker_status),
        suggested_symbol=text_field(suggested_symbol, suggested_status),
        shares=decimal_field(shares),
        average_cost=decimal_field(average_cost),
        position_type=DraftField(
            value=position_type,
            status=RecognitionFieldStatus.PRESENT
            if position_type is not None
            else RecognitionFieldStatus.MISSING,
        ),
        confidence=Decimal(confidence) if confidence is not None else None,
    )


class BrowserSmokeRecognitionProvider(RecognitionProvider):
    """返回固定 Text / Screenshot Draft，不执行真实 Vision Provider。"""

    def recognize(self, request: RecognitionInput) -> RecognitionResult:
        """按输入形式返回正常与 ambiguous 主流程 Fixture。"""

        if request.kind is RecognitionInputKind.TEXT:
            text = (request.text or "").upper()
            if "AMBIGUOUS" in text:
                row = _smoke_draft_row(
                    ticker="GOOG",
                    suggested_symbol="GOOG",
                    shares="2",
                    average_cost="180.25",
                    confidence="0.48",
                    ticker_status=RecognitionFieldStatus.AMBIGUOUS,
                    suggested_status=RecognitionFieldStatus.AMBIGUOUS,
                )
            else:
                row = _smoke_draft_row(
                    ticker="ADBE",
                    suggested_symbol="ADBE",
                    shares="3",
                    average_cost="260.50",
                )
            return RecognitionResult.success(
                RecognitionDraft(rows=(row,), input_kind=RecognitionInputKind.TEXT)
            )

        row = _smoke_draft_row(
            ticker="NVDA",
            suggested_symbol="NVDA",
            shares="4",
            # 用户提供的 IBKR 参考截图没有展示平均成本，Smoke 必须保留该缺失事实。
            average_cost=None,
        )
        return RecognitionResult.success(
            RecognitionDraft(rows=(row,), input_kind=RecognitionInputKind.SCREENSHOT)
        )


class BrowserSmokeQuoteReader:
    """为 Engineering Smoke 返回固定当前行情与历史日 K。"""

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        return MarketDataResult.success(
            MarketQuote(
                ticker=ticker,
                last_price=Decimal("250"),
                bid_price=Decimal("249.5"),
                ask_price=Decimal("250.5"),
                last_trade_at=NOW,
                quote_at=NOW,
                source="browser-smoke",
                feed="fixture",
                coverage=MarketDataCoverage.SINGLE_EXCHANGE,
                currency="USD",
                is_delayed=False,
                fetched_at=NOW,
            )
        )

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        """按请求窗口返回不访问网络的已完成日 K。"""

        query_end = query.end.astimezone(UTC)
        bars = tuple(
            OHLCVBar(
                timestamp=query_end - timedelta(days=offset),
                open=Decimal(str(240 + index * 4)),
                high=Decimal(str(244 + index * 4)),
                low=Decimal(str(238 + index * 4)),
                close=Decimal(str(242 + index * 4)),
                volume=1_000 + index * 100,
            )
            for index, offset in enumerate((3, 2, 1))
        )
        return MarketDataResult.success(
            HistoricalBars(
                ticker=query.ticker,
                timeframe="1Day",
                bars=bars,
                source="browser-smoke",
                feed="fixture",
                coverage=MarketDataCoverage.SINGLE_EXCHANGE,
                currency="USD",
                adjustment="ALL",
                fetched_at=NOW,
            )
        )


portfolio_service = BrowserSmokePortfolioService()
market_data_reader = BrowserSmokeQuoteReader()
portfolio_valuation_service = PortfolioValuationService(
    portfolio_service,
    market_data_reader,
    clock=lambda: NOW,
)
portfolio_chart_service = PortfolioChartService(
    portfolio_service,
    market_data_reader,
    clock=lambda: NOW,
)
portfolio_summary_service = PortfolioSummaryService(
    portfolio_service,
    portfolio_valuation_service,
)
investment_agent = BrowserSmokeInvestmentAgent()
conversation_store = BrowserSmokeConversationStore()
conversation_service = ConversationService(
    lambda: BrowserSmokeConversationUnitOfWork(conversation_store),
    agent=BrowserSmokeConversationAgent(),
    clock=lambda: NOW,
)
asset_metadata_service = AssetMetadataService(BrowserSmokeAssetMetadataProvider())
recognition_service = RecognitionService(BrowserSmokeRecognitionProvider())
auth_store = BrowserSmokeAuthStore()
auth_service = AuthService(
    lambda: BrowserSmokeAuthUnitOfWork(auth_store, portfolio_service),
    clock=lambda: datetime.now(UTC),
)
opening_import_service = OpeningImportService(
    auth_service,
    portfolio_service,
)

app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio_service
app.dependency_overrides[get_portfolio_valuation_service_dependency] = lambda: (
    portfolio_valuation_service
)
app.dependency_overrides[get_portfolio_summary_service_dependency] = lambda: (
    portfolio_summary_service
)
app.dependency_overrides[get_portfolio_chart_service_dependency] = lambda: portfolio_chart_service
app.dependency_overrides[get_investment_agent_dependency] = lambda: investment_agent
app.dependency_overrides[get_auth_service_dependency] = lambda: auth_service
app.dependency_overrides[get_conversation_auth_service_dependency] = lambda: auth_service
app.dependency_overrides[get_conversation_service_dependency] = lambda: conversation_service
app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_metadata_service
app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition_service
app.dependency_overrides[get_opening_import_service_dependency] = lambda: opening_import_service
