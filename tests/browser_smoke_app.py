"""M8 Human Browser Smoke 使用的确定性本地应用。"""

from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from time import sleep
from uuid import UUID

from position_pilot.application.errors import OpeningStateSealed, UserNotFound
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.portfolio_service import (
    CashAdjustmentResult,
    CreateUserCommand,
    InitializeOpeningPositionsCommand,
    RecordCashEventCommand,
    RecordTransactionCommand,
)
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    CashBalance,
    CashEvent,
    OpeningPosition,
    PortfolioState,
    Position,
    PositionType,
    Transaction,
    User,
    normalize_timestamp,
    rebuild_portfolio,
    resequence_cash_events,
    resequence_transactions,
)
from position_pilot.main import (
    app,
    get_investment_agent_dependency,
    get_portfolio_service_dependency,
)

USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
SLOW_USER = UUID("30000000-0000-4000-8000-000000000003")
EMPTY_USER = UUID("40000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)


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
    )


class BrowserSmokePortfolioService:
    """提供固定读取 Fixture 与可写的进程内 Portfolio。"""

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._transactions: dict[UUID, list[Transaction]] = {}
        self._cash_events: dict[UUID, list[CashEvent]] = {}
        self._opening_positions: dict[UUID, list[OpeningPosition]] = {}
        self._lock = RLock()

    def create_user(self, command: CreateUserCommand) -> User:
        """创建隔离的 Browser Smoke User。"""

        with self._lock:
            user = User.create(
                display_name=command.display_name,
                initial_cash=command.initial_cash,
            )
            self._users[user.id] = user
            self._transactions[user.id] = []
            self._cash_events[user.id] = []
            self._opening_positions[user.id] = []
            return user

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        """在首个经济记录前原子保存 Browser Smoke 期初仓位。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            if (
                self._opening_positions[user.id]
                or self._transactions[user.id]
                or self._cash_events[user.id]
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
            rebuild_portfolio(user, [], [], positions)
            self._opening_positions[user.id] = positions
            return tuple(
                sorted(positions, key=lambda item: (item.ticker, item.position_type.value))
            )

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction:
        """使用正式 Domain 规则追加 Browser Smoke Transaction。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            transactions = self._transactions[user.id]
            cash_events = self._cash_events[user.id]
            current_time = datetime.now(UTC)
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise InvalidPortfolioValue("Transaction occurred_at 不得晚于当前时间")
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
            ordered = resequence_transactions([*transactions, transaction])
            rebuild_portfolio(user, ordered, cash_events, self._opening_positions[user.id])
            self._transactions[user.id] = ordered
            return next(candidate for candidate in ordered if candidate.id == transaction.id)

    def record_cash_event(self, command: RecordCashEventCommand) -> CashAdjustmentResult:
        """使用正式 Domain 规则追加 Browser Smoke Cash Event。"""

        with self._lock:
            user = self._require_mutable_user(command.user_id)
            transactions = self._transactions[user.id]
            cash_events = self._cash_events[user.id]
            current_time = datetime.now(UTC)
            occurred_at = normalize_timestamp(command.occurred_at or current_time)
            if occurred_at > current_time:
                raise InvalidPortfolioValue("Cash Event occurred_at 不得晚于当前时间")
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
        """返回 Browser Smoke 的完整期初仓位列表。"""

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
        """返回 Browser Smoke 的完整交易列表。"""

        with self._lock:
            if user_id in self._users:
                return tuple(self._transactions[user_id])
        if user_id in {USER_A, USER_B, SLOW_USER, EMPTY_USER}:
            return ()
        raise UserNotFound(user_id)

    def list_cash_events(self, user_id: UUID) -> tuple[CashEvent, ...]:
        """返回 Browser Smoke 的完整现金事件列表。"""

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


class BrowserSmokeInvestmentAgent:
    """按问题文本返回 OK、降级、失败、延迟与注入场景。"""

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


portfolio_service = BrowserSmokePortfolioService()
investment_agent = BrowserSmokeInvestmentAgent()

app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio_service
app.dependency_overrides[get_investment_agent_dependency] = lambda: investment_agent
