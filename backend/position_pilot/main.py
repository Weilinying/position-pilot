"""FastAPI 应用入口。"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from position_pilot.application.auth_service import (
    Account,
    AuthService,
    LoginCommand,
    RegisterAccountCommand,
    SetupPortfolioCommand,
)
from position_pilot.application.errors import (
    AuthenticationRequired,
    EmailAlreadyRegistered,
    InvalidCredentials,
    OpeningStateSealed,
    PortfolioAlreadyExists,
    UserNotFound,
)
from position_pilot.application.investment_agent import (
    MAX_QUESTION_LENGTH,
    ContextSource,
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.portfolio_service import (
    InitializeOpeningPositionsCommand,
    OpeningPositionInput,
    PortfolioService,
    RecordCashEventCommand,
    RecordTransactionCommand,
)
from position_pilot.bootstrap import get_auth_service, get_investment_agent, get_portfolio_service
from position_pilot.domain.errors import InsufficientCash, InsufficientShares, InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    CashEvent,
    CashEventType,
    OpeningPosition,
    PortfolioState,
    PositionType,
    Transaction,
    TransactionAction,
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
SESSION_COOKIE_NAME = "positionpilot_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


class HealthResponse(BaseModel):
    """应用存活检查的稳定响应。"""

    status: str


class InvestmentQuestionRequest(BaseModel):
    """M3 投资问答 Vertical Slice 的稳定输入。"""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        """拒绝只包含空白的问题，并避免把格式清理交给 LLM。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("question 不能为空")
        return normalized


class ContextSourceResponse(BaseModel):
    """API 暴露的事实来源与获取状态。"""

    model_config = ConfigDict(from_attributes=True)

    type: ContextSourceType
    status: str
    ticker: str | None = None
    provider: str | None = None
    feed: str | None = None
    market_timestamp: datetime | None = None
    fetched_at: datetime | None = None


class InvestmentQuestionResponse(BaseModel):
    """包含确定性状态、自然语言回答和 Source Tracking。"""

    status: InvestmentResponseStatus
    answer: str
    sources: tuple[ContextSourceResponse, ...]


class ApiErrorDetail(BaseModel):
    """无法形成 Final Answer 时的稳定错误内容。"""

    code: str
    message: str


class RegisterRequest(BaseModel):
    """创建本地 Account 的公开输入。"""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    """登录本地 Account 的公开输入。"""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class AccountResponse(BaseModel):
    """不包含 Password、Token 或内部 User ID 的 Account View。"""

    email: str
    display_name: str
    portfolio_ready: bool


class AuthSessionResponse(BaseModel):
    """注册、登录与 Session Recovery 的稳定响应。"""

    account: AccountResponse


class CreatePortfolioRequest(BaseModel):
    """创建本地 Portfolio Owner 的最小输入。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    initial_cash: Decimal = Field(ge=0, max_digits=28, decimal_places=8)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """拒绝只包含空白的名称，并与领域规范化保持一致。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name 不能为空")
        return normalized


class PortfolioCreatedResponse(BaseModel):
    """创建成功后返回的本地 Portfolio 标识。"""

    user_id: UUID
    display_name: str
    initial_cash: Decimal
    created_at: datetime


class CashEventRequest(BaseModel):
    """Portfolio 创建后追加不可变现金调整的输入。"""

    event_type: CashEventType
    amount: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    occurred_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """历史补录时间必须带时区，空值由 Application Clock 补齐。"""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at 必须包含时区")
        return value


class CashEventResponse(BaseModel):
    """API 暴露的不可变 Cash Event Ledger Record。"""

    id: UUID
    user_id: UUID
    sequence: int
    event_type: CashEventType
    amount: Decimal
    occurred_at: datetime
    reason: str | None


class CashAdjustmentResponse(BaseModel):
    """Cash Event 写入结果及同事务重建后的现金状态。"""

    cash_event: CashEventResponse
    available_cash: Decimal


class TransactionRequest(BaseModel):
    """追加不可变 Transaction 的显式用户输入。"""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=100)
    action: TransactionAction
    price: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    shares: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    position_type: PositionType | None = None
    occurred_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """历史补录时间必须带时区，空值由 Application Clock 补齐。"""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at 必须包含时区")
        return value


class LedgerTransactionResponse(BaseModel):
    """API 暴露的不可变 Transaction Ledger Record。"""

    id: UUID
    user_id: UUID
    sequence: int
    ticker: str
    action: TransactionAction
    price: Decimal
    shares: Decimal
    amount: Decimal
    commission: Decimal
    fee_schedule: str
    position_type: PositionType
    occurred_at: datetime
    reason: str | None


class TransactionWriteResponse(BaseModel):
    """成功追加后返回由后端完整派生的 Transaction。"""

    transaction: LedgerTransactionResponse


class OpeningPositionRequest(BaseModel):
    """Opening State 中单个 Existing Position 的输入。"""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=100)
    shares: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    average_cost: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    position_type: PositionType | None = None


class OpeningPositionsRequest(BaseModel):
    """一次性原子提交的完整 Existing Positions Draft。"""

    model_config = ConfigDict(extra="forbid")

    positions: tuple[OpeningPositionRequest, ...] = Field(min_length=1, max_length=100)


class PortfolioSetupRequest(BaseModel):
    """已认证 Account 的一次性 Portfolio Setup。"""

    model_config = ConfigDict(extra="forbid")

    initial_cash: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)
    opening_positions: tuple[OpeningPositionRequest, ...] = Field(
        default=(),
        max_length=100,
    )


class OpeningPositionResponse(BaseModel):
    """API 暴露的 immutable Opening Position Starting Fact。"""

    id: UUID
    user_id: UUID
    ticker: str
    shares: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    position_type: PositionType
    recorded_at: datetime


class OpeningPositionsWriteResponse(BaseModel):
    """Opening State 初始化后的完整稳定结果。"""

    opening_positions: tuple[OpeningPositionResponse, ...]
    items_are_complete: bool = True


class OpeningPositionListResponse(BaseModel):
    """完整只读 Opening Position List。"""

    items: tuple[OpeningPositionResponse, ...]
    items_are_complete: bool = True


class TransactionListResponse(BaseModel):
    """完整只读 Transaction List。"""

    items: tuple[LedgerTransactionResponse, ...]
    items_are_complete: bool = True


class CashEventListResponse(BaseModel):
    """完整只读 Cash Event List。"""

    items: tuple[CashEventResponse, ...]
    items_are_complete: bool = True


class PositionResponse(BaseModel):
    """只读 Portfolio Snapshot 中保留仓位意图的确定性持仓。"""

    ticker: str
    position_type: PositionType
    shares: Decimal
    average_cost: Decimal
    cost_basis: Decimal


class PortfolioSnapshotResponse(BaseModel):
    """从完整 Ledger 确定性重建的当前 Portfolio Snapshot。"""

    user_id: UUID
    available_cash: Decimal
    positions_are_complete: bool
    positions: tuple[PositionResponse, ...]


app = FastAPI(title="PositionPilot")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/app/", include_in_schema=False)
def get_product_interface() -> FileResponse:
    """返回 M7 本地同源产品界面。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """返回应用进程的存活状态，不检查外部依赖。"""

    return HealthResponse(status="ok")


def get_investment_agent_dependency() -> InvestmentAgent:
    """延迟装配外部依赖，允许测试安全替换。"""

    return get_investment_agent()


def get_portfolio_service_dependency() -> PortfolioService:
    """延迟装配 Portfolio Service，允许 API Contract Test 替换。"""

    return get_portfolio_service()


def get_auth_service_dependency() -> AuthService:
    """延迟装配 Auth Service，允许 API 与 Browser Test 安全替换。"""

    return get_auth_service()


def get_current_account_dependency(
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> Account:
    """只从 HttpOnly Cookie Session 解析当前 Account。"""

    try:
        return auth_service.authenticate(session_token)
    except AuthenticationRequired as error:
        _raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            ApiErrorDetail(code="AUTHENTICATION_REQUIRED", message=str(error)),
        )


def _set_session_cookie(response: Response, token: str) -> None:
    """设置只适用于 loopback HTTP 的最小持久 Session Cookie。"""

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def _account_response(account: Account) -> AccountResponse:
    return AccountResponse(
        email=account.email,
        display_name=account.display_name,
        portfolio_ready=account.portfolio_user_id is not None,
    )


def _require_portfolio_user(account: Account) -> UUID:
    if account.portfolio_user_id is None:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(
                code="PORTFOLIO_SETUP_REQUIRED",
                message="请先完成 Portfolio Setup",
            ),
        )
    return account.portfolio_user_id


def _require_portfolio_owner(account: Account, user_id: UUID) -> None:
    if account.portfolio_user_id != user_id:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="PORTFOLIO_NOT_FOUND", message="Portfolio 不存在"),
        )


@app.post(
    "/v1/auth/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_account(
    request: RegisterRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
) -> AuthSessionResponse:
    """创建本地 Account 并立即建立持久 Session。"""

    try:
        result = auth_service.register(
            RegisterAccountCommand(
                email=request.email,
                password=request.password,
                display_name=request.display_name,
            )
        )
    except EmailAlreadyRegistered as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="EMAIL_ALREADY_REGISTERED", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_ACCOUNT", message=str(error)),
        )
    _set_session_cookie(response, result.token)
    return AuthSessionResponse(account=_account_response(result.account))


@app.post("/v1/auth/login", response_model=AuthSessionResponse)
def login_account(
    request: LoginRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> AuthSessionResponse:
    """校验 Email / Password，并使用新 Token 替代当前 Browser Session。"""

    try:
        result = auth_service.login(
            LoginCommand(email=request.email, password=request.password),
            current_session_token=session_token,
        )
    except (InvalidCredentials, InvalidPortfolioValue) as error:
        _raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            ApiErrorDetail(code="INVALID_CREDENTIALS", message=str(error)),
        )
    _set_session_cookie(response, result.token)
    return AuthSessionResponse(account=_account_response(result.account))


@app.post("/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_account(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> None:
    """幂等撤销当前 Session 并清除 Browser Cookie。"""

    auth_service.logout(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@app.get("/v1/auth/session", response_model=AuthSessionResponse)
def get_auth_session(
    account: Annotated[Account, Depends(get_current_account_dependency)],
) -> AuthSessionResponse:
    """恢复当前非敏感 Account View。"""

    return AuthSessionResponse(account=_account_response(account))


@app.post(
    "/v1/portfolio",
    response_model=PortfolioSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup_account_portfolio(
    request: PortfolioSetupRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> PortfolioSnapshotResponse:
    """为当前 Account 原子创建唯一 Portfolio 与可选 Opening State。"""

    try:
        user = auth_service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=account.id,
                initial_cash=request.initial_cash,
                opening_positions=tuple(
                    OpeningPositionInput(
                        ticker=position.ticker,
                        shares=position.shares,
                        average_cost=position.average_cost,
                        position_type=position.position_type,
                    )
                    for position in request.opening_positions
                ),
            )
        )
        portfolio = portfolio_service.get_portfolio(user.id)
    except PortfolioAlreadyExists as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="PORTFOLIO_ALREADY_EXISTS", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_PORTFOLIO", message=str(error)),
        )
    return _portfolio_snapshot_response(portfolio)


@app.post(
    "/v1/portfolios",
    response_model=PortfolioCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"description": "Portfolio 创建输入不满足领域约束"}},
)
def create_portfolio(
    request: CreatePortfolioRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    auth_service: Annotated[AuthService, Depends(get_auth_service_dependency)],
) -> PortfolioCreatedResponse:
    """兼容旧 Contract，但只允许当前 Account 创建其唯一 Portfolio。"""

    try:
        user = auth_service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=account.id,
                initial_cash=request.initial_cash,
            )
        )
    except PortfolioAlreadyExists as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="PORTFOLIO_ALREADY_EXISTS", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_PORTFOLIO", message=str(error)),
        )

    return PortfolioCreatedResponse(
        user_id=user.id,
        display_name=user.display_name,
        initial_cash=user.initial_cash,
        created_at=user.created_at,
    )


@app.get(
    "/v1/portfolios/{user_id}",
    response_model=PortfolioSnapshotResponse,
    responses={404: {"description": "Portfolio User 不存在"}},
)
def get_portfolio_snapshot(
    user_id: UUID,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> PortfolioSnapshotResponse:
    """返回 Ledger 重放产生的完整当前持仓集合。"""

    _require_portfolio_owner(account, user_id)
    try:
        portfolio = portfolio_service.get_portfolio(user_id)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )

    return _portfolio_snapshot_response(portfolio)


@app.post(
    "/v1/portfolios/{user_id}/opening-positions",
    response_model=OpeningPositionsWriteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Portfolio User 不存在"},
        409: {"description": "Opening State 已封闭"},
        422: {"description": "Opening Position 输入不满足领域约束"},
    },
)
def initialize_opening_positions(
    user_id: UUID,
    request: OpeningPositionsRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> OpeningPositionsWriteResponse:
    """在首个经济 Mutation 前原子初始化 Existing Positions。"""

    _require_portfolio_owner(account, user_id)
    try:
        opening_positions = portfolio_service.initialize_opening_positions(
            InitializeOpeningPositionsCommand(
                user_id=user_id,
                positions=tuple(
                    OpeningPositionInput(
                        ticker=position.ticker,
                        shares=position.shares,
                        average_cost=position.average_cost,
                        position_type=position.position_type,
                    )
                    for position in request.positions
                ),
            )
        )
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    except OpeningStateSealed as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="OPENING_STATE_SEALED", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_OPENING_STATE", message=str(error)),
        )

    return OpeningPositionsWriteResponse(
        opening_positions=tuple(
            _opening_position_response(position) for position in opening_positions
        )
    )


@app.get(
    "/v1/portfolios/{user_id}/opening-positions",
    response_model=OpeningPositionListResponse,
    responses={404: {"description": "Portfolio User 不存在"}},
)
def list_opening_positions(
    user_id: UUID,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> OpeningPositionListResponse:
    """返回不带经济 sequence 的完整 Opening Position List。"""

    _require_portfolio_owner(account, user_id)
    try:
        opening_positions = portfolio_service.list_opening_positions(user_id)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    return OpeningPositionListResponse(
        items=tuple(
            _opening_position_response(position)
            for position in sorted(
                opening_positions,
                key=lambda item: (item.ticker, item.position_type.value),
            )
        )
    )


@app.post(
    "/v1/portfolios/{user_id}/transactions",
    response_model=TransactionWriteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Portfolio User 不存在"},
        409: {"description": "现金或指定仓位 Shares 不足"},
        422: {"description": "Transaction 输入不满足领域约束"},
    },
)
def record_transaction(
    user_id: UUID,
    request: TransactionRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> TransactionWriteResponse:
    """追加 BUY / SELL，并返回后端派生的不可变 Ledger Record。"""

    _require_portfolio_owner(account, user_id)
    try:
        transaction = portfolio_service.record_transaction(
            RecordTransactionCommand(
                user_id=user_id,
                ticker=request.ticker,
                action=request.action,
                price=request.price,
                shares=request.shares,
                position_type=request.position_type,
                occurred_at=request.occurred_at,
                reason=request.reason,
            )
        )
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    except InsufficientCash as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="INSUFFICIENT_CASH", message=str(error)),
        )
    except InsufficientShares as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="INSUFFICIENT_SHARES", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_TRANSACTION", message=str(error)),
        )

    return TransactionWriteResponse(transaction=_transaction_response(transaction))


@app.get(
    "/v1/portfolios/{user_id}/transactions",
    response_model=TransactionListResponse,
    responses={404: {"description": "Portfolio User 不存在"}},
)
def list_transactions(
    user_id: UUID,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> TransactionListResponse:
    """按经济 sequence 返回完整只读 Transaction List。"""

    _require_portfolio_owner(account, user_id)
    try:
        transactions = portfolio_service.list_transactions(user_id)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    return TransactionListResponse(
        items=tuple(
            _transaction_response(transaction)
            for transaction in sorted(transactions, key=lambda item: item.sequence)
        )
    )


@app.post(
    "/v1/portfolios/{user_id}/cash-events",
    response_model=CashAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Portfolio User 不存在"},
        409: {"description": "Withdrawal 超过当前可用现金"},
        422: {"description": "Cash Event 输入不满足领域约束"},
    },
)
def record_cash_event(
    user_id: UUID,
    request: CashEventRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> CashAdjustmentResponse:
    """追加 DEPOSIT / WITHDRAWAL 并返回确定性 Cash Snapshot。"""

    _require_portfolio_owner(account, user_id)
    try:
        result = portfolio_service.record_cash_event(
            RecordCashEventCommand(
                user_id=user_id,
                event_type=request.event_type,
                amount=request.amount,
                occurred_at=request.occurred_at,
                reason=request.reason,
            )
        )
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    except InsufficientCash as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="INSUFFICIENT_CASH", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_CASH_EVENT", message=str(error)),
        )

    return CashAdjustmentResponse(
        cash_event=_cash_event_response(result.cash_event),
        available_cash=result.portfolio.cash.available_cash,
    )


@app.get(
    "/v1/portfolios/{user_id}/cash-events",
    response_model=CashEventListResponse,
    responses={404: {"description": "Portfolio User 不存在"}},
)
def list_cash_events(
    user_id: UUID,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> CashEventListResponse:
    """按经济 sequence 返回完整只读 Cash Event List。"""

    _require_portfolio_owner(account, user_id)
    try:
        cash_events = portfolio_service.list_cash_events(user_id)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    return CashEventListResponse(
        items=tuple(
            _cash_event_response(cash_event)
            for cash_event in sorted(cash_events, key=lambda item: item.sequence)
        )
    )


@app.get("/v1/portfolio", response_model=PortfolioSnapshotResponse)
def get_current_portfolio_snapshot(
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> PortfolioSnapshotResponse:
    """返回当前 Session Account 的唯一 Portfolio Snapshot。"""

    return get_portfolio_snapshot(
        _require_portfolio_user(account),
        account,
        portfolio_service,
    )


@app.post(
    "/v1/portfolio/opening-positions",
    response_model=OpeningPositionsWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_current_opening_positions(
    request: OpeningPositionsRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> OpeningPositionsWriteResponse:
    """为当前 Session Portfolio 初始化一次性 Existing Positions。"""

    return initialize_opening_positions(
        _require_portfolio_user(account),
        request,
        account,
        portfolio_service,
    )


@app.get("/v1/portfolio/opening-positions", response_model=OpeningPositionListResponse)
def list_current_opening_positions(
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> OpeningPositionListResponse:
    """返回当前 Session Portfolio 的完整 Opening State。"""

    return list_opening_positions(
        _require_portfolio_user(account),
        account,
        portfolio_service,
    )


@app.post(
    "/v1/portfolio/transactions",
    response_model=TransactionWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_current_transaction(
    request: TransactionRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> TransactionWriteResponse:
    """为当前 Session Portfolio 追加 BUY / SELL。"""

    return record_transaction(
        _require_portfolio_user(account),
        request,
        account,
        portfolio_service,
    )


@app.get("/v1/portfolio/transactions", response_model=TransactionListResponse)
def list_current_transactions(
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> TransactionListResponse:
    """返回当前 Session Portfolio 的完整 Transaction List。"""

    return list_transactions(
        _require_portfolio_user(account),
        account,
        portfolio_service,
    )


@app.post(
    "/v1/portfolio/cash-events",
    response_model=CashAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_current_cash_event(
    request: CashEventRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> CashAdjustmentResponse:
    """为当前 Session Portfolio 追加 DEPOSIT / WITHDRAWAL。"""

    return record_cash_event(
        _require_portfolio_user(account),
        request,
        account,
        portfolio_service,
    )


@app.get("/v1/portfolio/cash-events", response_model=CashEventListResponse)
def list_current_cash_events(
    account: Annotated[Account, Depends(get_current_account_dependency)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> CashEventListResponse:
    """返回当前 Session Portfolio 的完整 Cash Event List。"""

    return list_cash_events(
        _require_portfolio_user(account),
        account,
        portfolio_service,
    )


@app.post(
    "/v1/investment/questions",
    response_model=InvestmentQuestionResponse,
    responses={
        404: {"description": "Portfolio User 不存在"},
        502: {"description": "Agent / LLM Contract 无法形成回答"},
        503: {"description": "LLM Provider 当前无法形成回答"},
    },
)
def answer_investment_question(
    request: InvestmentQuestionRequest,
    account: Annotated[Account, Depends(get_current_account_dependency)],
    agent: Annotated[InvestmentAgent, Depends(get_investment_agent_dependency)],
) -> InvestmentQuestionResponse:
    """读取 Structured State 并执行最小 Investment Agent Vertical Slice。"""

    user_id = _require_portfolio_user(account)
    try:
        result = agent.answer(user_id, request.question)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    if isinstance(result, InvestmentRequestFailure):
        _raise_request_failure(result)
    assert isinstance(result, InvestmentAnswer)
    return InvestmentQuestionResponse(
        status=result.status,
        answer=result.answer,
        sources=tuple(_source_response(source) for source in result.sources),
    )


def _opening_position_response(position: OpeningPosition) -> OpeningPositionResponse:
    return OpeningPositionResponse(
        id=position.id,
        user_id=position.user_id,
        ticker=position.ticker,
        shares=position.shares,
        average_cost=position.average_cost,
        cost_basis=position.cost_basis,
        position_type=position.position_type,
        recorded_at=position.recorded_at,
    )


def _portfolio_snapshot_response(portfolio: PortfolioState) -> PortfolioSnapshotResponse:
    """把确定性 Portfolio State 映射为稳定 Public Response。"""

    positions = tuple(
        PositionResponse(
            ticker=position.ticker,
            position_type=position.position_type,
            shares=position.shares,
            average_cost=position.average_cost,
            cost_basis=position.cost_basis,
        )
        for position in sorted(
            portfolio.positions,
            key=lambda item: (item.ticker, item.position_type.value),
        )
    )
    return PortfolioSnapshotResponse(
        user_id=portfolio.user_id,
        available_cash=portfolio.cash.available_cash,
        positions_are_complete=True,
        positions=positions,
    )


def _transaction_response(transaction: Transaction) -> LedgerTransactionResponse:
    return LedgerTransactionResponse(
        id=transaction.id,
        user_id=transaction.user_id,
        sequence=transaction.sequence,
        ticker=transaction.ticker,
        action=transaction.action,
        price=transaction.price,
        shares=transaction.shares,
        amount=transaction.amount,
        commission=transaction.commission,
        fee_schedule=transaction.fee_schedule,
        position_type=transaction.position_type,
        occurred_at=transaction.occurred_at,
        reason=transaction.reason,
    )


def _cash_event_response(cash_event: CashEvent) -> CashEventResponse:
    return CashEventResponse(
        id=cash_event.id,
        user_id=cash_event.user_id,
        sequence=cash_event.sequence,
        event_type=cash_event.event_type,
        amount=cash_event.amount,
        occurred_at=cash_event.occurred_at,
        reason=cash_event.reason,
    )


def _source_response(source: ContextSource) -> ContextSourceResponse:
    return ContextSourceResponse.model_validate(source)


def _raise_request_failure(failure: InvestmentRequestFailure) -> None:
    if failure.code is InvestmentFailureCode.INVALID_QUESTION:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code=failure.code.value, message=failure.message),
        )
    provider_unavailable_codes = {
        InvestmentFailureCode.LLM_AUTHENTICATION_FAILED,
        InvestmentFailureCode.LLM_RATE_LIMITED,
        InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
    }
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if failure.code in provider_unavailable_codes
        else status.HTTP_502_BAD_GATEWAY
    )
    _raise_api_error(
        status_code,
        ApiErrorDetail(code=failure.code.value, message=failure.message),
    )


def _raise_api_error(status_code: int, detail: ApiErrorDetail) -> NoReturn:
    raise HTTPException(status_code=status_code, detail=detail.model_dump())
