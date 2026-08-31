"""M8 Engineering Browser Smoke 使用的确定性本地应用替身。

该模块只用于人工检查和定向 Engineering Smoke。它替换真实数据库与真实
Investment Agent，不是生产入口、不是自动化 E2E，也不构成真实模型验收证据。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from time import sleep
from types import TracebackType
from typing import Self
from uuid import UUID

from fastapi import Request
from starlette.responses import RedirectResponse, Response

from position_pilot.application.auth_service import Account, AuthService, AuthSession
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
    get_auth_service_dependency,
    get_investment_agent_dependency,
    get_portfolio_service_dependency,
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
            return user

    def add_auth_user(self, user: User) -> None:
        """把 Auth Service 创建的 User 接入同一个 Engineering Smoke Portfolio Store。"""

        with self._lock:
            self._users[user.id] = user
            self._transactions[user.id] = []
            self._cash_events[user.id] = []
            self._opening_positions[user.id] = []

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
        """使用正式 Domain 规则追加 Engineering Smoke Transaction。"""

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
        """使用正式 Domain 规则追加 Engineering Smoke Cash Event。"""

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


portfolio_service = BrowserSmokePortfolioService()
investment_agent = BrowserSmokeInvestmentAgent()
auth_store = BrowserSmokeAuthStore()
auth_service = AuthService(
    lambda: BrowserSmokeAuthUnitOfWork(auth_store, portfolio_service),
    clock=lambda: datetime.now(UTC),
)

app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio_service
app.dependency_overrides[get_investment_agent_dependency] = lambda: investment_agent
app.dependency_overrides[get_auth_service_dependency] = lambda: auth_service
