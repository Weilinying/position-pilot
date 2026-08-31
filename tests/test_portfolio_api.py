"""Portfolio Public API Contract 测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import Account, SetupPortfolioCommand
from position_pilot.application.errors import OpeningStateSealed, UserNotFound
from position_pilot.application.portfolio_service import (
    CashAdjustmentResult,
    InitializeOpeningPositionsCommand,
    RecordCashEventCommand,
    RecordTransactionCommand,
)
from position_pilot.domain.errors import (
    InsufficientCash,
    InsufficientShares,
    InvalidPortfolioValue,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    CashEvent,
    CashEventType,
    OpeningPosition,
    PortfolioState,
    Position,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
)
from position_pilot.main import (
    app,
    get_auth_service_dependency,
    get_current_account_dependency,
    get_portfolio_service_dependency,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000002")
TRANSACTION_ID = UUID("00000000-0000-0000-0000-000000000003")
OPENING_ID = UUID("00000000-0000-0000-0000-000000000004")
OCCURRED_AT = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")


def make_account(*, portfolio_user_id: UUID | None = USER_ID) -> Account:
    """创建不经过真实 Session / Database 的已认证 Account。"""

    return Account(
        id=ACCOUNT_ID,
        email="api@example.com",
        display_name="My Portfolio",
        password_hash="not-returned",
        portfolio_user_id=portfolio_user_id,
        created_at=OCCURRED_AT,
    )


@dataclass(slots=True)
class FakePortfolioService:
    """返回固定 Cash Adjustment Result，并记录 API Command。"""

    result: CashAdjustmentResult | Exception
    commands: list[RecordCashEventCommand] = field(default_factory=list)

    def record_cash_event(self, command: RecordCashEventCommand) -> CashAdjustmentResult:
        self.commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakePortfolioSetup:
    """返回固定 User，并记录 Account Portfolio Setup Command。"""

    result: User | Exception
    commands: list[SetupPortfolioCommand] = field(default_factory=list)

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        self.commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakeTransactionWriter:
    """返回固定 Transaction，并记录 API Command。"""

    result: Transaction | Exception
    commands: list[RecordTransactionCommand] = field(default_factory=list)

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction:
        self.commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakePortfolioReader:
    """返回固定 Portfolio State，并记录只读查询。"""

    result: PortfolioState | Exception
    user_ids: list[UUID] = field(default_factory=list)

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        self.user_ids.append(user_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakeOpeningPositionService:
    """返回固定 Opening Positions，并记录初始化 Command 或查询。"""

    result: tuple[OpeningPosition, ...] | Exception
    commands: list[InitializeOpeningPositionsCommand] = field(default_factory=list)
    user_ids: list[UUID] = field(default_factory=list)

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        self.commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def list_opening_positions(self, user_id: UUID) -> tuple[OpeningPosition, ...]:
        self.user_ids.append(user_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakeTransactionListReader:
    """返回固定 Transaction List。"""

    result: tuple[Transaction, ...] | Exception

    def list_transactions(self, user_id: UUID) -> tuple[Transaction, ...]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class FakeCashEventListReader:
    """返回固定 Cash Event List。"""

    result: tuple[CashEvent, ...] | Exception

    def list_cash_events(self, user_id: UUID) -> tuple[CashEvent, ...]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试后恢复 Cash Adjustment Dependency Override。"""

    app.dependency_overrides[get_current_account_dependency] = make_account
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_result() -> CashAdjustmentResult:
    """创建 Deposit 500 后的固定结果。"""

    user = User.create(
        user_id=USER_ID,
        display_name="API User",
        initial_cash=Decimal("1000"),
        created_at=datetime(2026, 8, 20, 8, 0, tzinfo=UTC),
    )
    cash_event = CashEvent.create(
        cash_event_id=EVENT_ID,
        user_id=USER_ID,
        sequence=1,
        event_type=CashEventType.DEPOSIT,
        amount=Decimal("500"),
        occurred_at=OCCURRED_AT,
        reason="追加投资预算",
    )
    return CashAdjustmentResult(
        cash_event=cash_event,
        portfolio=rebuild_portfolio(user, [], [cash_event]),
    )


def make_transaction() -> Transaction:
    """创建 API Response 使用的固定 BUY Ledger Record。"""

    return Transaction.create(
        transaction_id=TRANSACTION_ID,
        user_id=USER_ID,
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("180.25"),
        shares=Decimal("2"),
        position_type=PositionType.LONG_TERM,
        occurred_at=OCCURRED_AT,
        reason="Initial long-term position",
    )


def make_opening_position(
    *,
    ticker: str = "GOOG",
    position_type: PositionType = PositionType.UNSPECIFIED,
) -> OpeningPosition:
    """创建 API Response 使用的固定 Opening Position。"""

    return OpeningPosition.create(
        opening_position_id=OPENING_ID,
        user_id=USER_ID,
        ticker=ticker,
        shares=Decimal("2"),
        average_cost=Decimal("100"),
        position_type=position_type,
        recorded_at=OCCURRED_AT,
    )


def override_service(service: object) -> None:
    """避免 API Contract Test 读取真实数据库。"""

    app.dependency_overrides[get_portfolio_service_dependency] = lambda: service


def override_auth_service(service: object) -> None:
    """避免兼容 Portfolio Create Contract 读取真实 Auth Database。"""

    app.dependency_overrides[get_auth_service_dependency] = lambda: service


def make_portfolio_state(*, positions: tuple[Position, ...] | None = None) -> PortfolioState:
    """创建包含稳定 Decimal 与可控持仓顺序的只读 Snapshot。"""

    return PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(
            user_id=USER_ID,
            initial_cash=Decimal("2000.00000000"),
            available_cash=Decimal("1679.30000000"),
        ),
        positions=(
            positions
            if positions is not None
            else (
                Position(
                    ticker="GOOG",
                    position_type=PositionType.SWING,
                    shares=Decimal("1.00000000"),
                    cost_basis=Decimal("120.35000000"),
                    average_cost=Decimal("120.35000000"),
                ),
                Position(
                    ticker="GOOG",
                    position_type=PositionType.LONG_TERM,
                    shares=Decimal("2.00000000"),
                    cost_basis=Decimal("200.35000000"),
                    average_cost=Decimal("100.17500000"),
                ),
            )
        ),
        transaction_count=2,
    )


def test_creates_local_portfolio_and_returns_server_identity(client: TestClient) -> None:
    """Create API 只接收名称与初始现金，并返回 Server 生成的标识。"""

    user = User.create(
        user_id=USER_ID,
        display_name="My Portfolio",
        initial_cash=Decimal("10000"),
        created_at=OCCURRED_AT,
    )
    service = FakePortfolioSetup(user)
    override_auth_service(service)
    app.dependency_overrides[get_current_account_dependency] = lambda: make_account(
        portfolio_user_id=None
    )

    response = client.post(
        "/v1/portfolios",
        json={"display_name": "  My Portfolio  ", "initial_cash": "10000"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(USER_ID),
        "display_name": "My Portfolio",
        "initial_cash": "10000.00000000",
        "created_at": "2026-08-25T08:30:00Z",
    }
    assert service.commands == [
        SetupPortfolioCommand(account_id=ACCOUNT_ID, initial_cash=Decimal("10000"))
    ]


def test_maps_invalid_portfolio_creation_to_stable_422(client: TestClient) -> None:
    """领域创建失败应保持稳定错误 Code。"""

    service = FakePortfolioSetup(InvalidPortfolioValue("initial_cash 无效"))
    override_auth_service(service)
    app.dependency_overrides[get_current_account_dependency] = lambda: make_account(
        portfolio_user_id=None
    )

    response = client.post(
        "/v1/portfolios",
        json={"display_name": "My Portfolio", "initial_cash": "10"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {"code": "INVALID_PORTFOLIO", "message": "initial_cash 无效"}
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "", "initial_cash": "10"},
        {"display_name": "   ", "initial_cash": "10"},
        {"display_name": "My Portfolio", "initial_cash": "-1"},
        {"display_name": "My Portfolio", "initial_cash": "1.000000001"},
        {
            "display_name": "My Portfolio",
            "initial_cash": "10",
            "user_id": str(USER_ID),
        },
    ],
)
def test_rejects_invalid_portfolio_creation_before_service_call(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    """非法名称或初始现金不得进入 Application Service。"""

    user = User.create(
        user_id=USER_ID,
        display_name="My Portfolio",
        initial_cash=Decimal("10"),
        created_at=OCCURRED_AT,
    )
    service = FakePortfolioSetup(user)
    override_auth_service(service)
    app.dependency_overrides[get_current_account_dependency] = lambda: make_account(
        portfolio_user_id=None
    )

    response = client.post("/v1/portfolios", json=payload)

    assert response.status_code == 422
    assert service.commands == []


def test_returns_complete_portfolio_snapshot_with_stable_position_order(
    client: TestClient,
) -> None:
    """只读 API 应保持 Decimal 精度并独立展示两类仓位。"""

    service = FakePortfolioReader(make_portfolio_state())
    override_service(service)

    response = client.get(f"/v1/portfolios/{USER_ID}")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(USER_ID),
        "available_cash": "1679.30000000",
        "positions_are_complete": True,
        "positions": [
            {
                "ticker": "GOOG",
                "position_type": "LONG_TERM",
                "shares": "2.00000000",
                "average_cost": "100.17500000",
                "cost_basis": "200.35000000",
            },
            {
                "ticker": "GOOG",
                "position_type": "SWING",
                "shares": "1.00000000",
                "average_cost": "120.35000000",
                "cost_basis": "120.35000000",
            },
        ],
    }
    assert service.user_ids == [USER_ID]


def test_returns_empty_portfolio_as_complete_snapshot(client: TestClient) -> None:
    """空持仓仍是成功加载的完整当前集合。"""

    override_service(FakePortfolioReader(make_portfolio_state(positions=())))

    response = client.get(f"/v1/portfolios/{USER_ID}")

    assert response.status_code == 200
    assert response.json()["positions_are_complete"] is True
    assert response.json()["positions"] == []


def test_maps_missing_portfolio_snapshot_user_to_404(client: TestClient) -> None:
    """未知 User 应使用稳定错误 Contract。"""

    service = FakePortfolioReader(UserNotFound(USER_ID))
    override_service(service)

    response = client.get(f"/v1/portfolios/{USER_ID}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "USER_NOT_FOUND", "message": "Portfolio User 不存在"}
    }
    assert service.user_ids == [USER_ID]


def test_initializes_opening_positions_without_sequence_or_cash_effect(client: TestClient) -> None:
    """Opening API 应返回派生 Cost Basis，并让缺省类型保持 UNSPECIFIED。"""

    opening_position = make_opening_position()
    service = FakeOpeningPositionService((opening_position,))
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/opening-positions",
        json={
            "positions": [
                {
                    "ticker": "goog",
                    "shares": "2",
                    "average_cost": "100",
                }
            ]
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "opening_positions": [
            {
                "id": str(OPENING_ID),
                "user_id": str(USER_ID),
                "ticker": "GOOG",
                "shares": "2.00000000",
                "average_cost": "100.00000000",
                "cost_basis": "200.00000000",
                "position_type": "UNSPECIFIED",
                "recorded_at": "2026-08-25T08:30:00Z",
            }
        ],
        "items_are_complete": True,
    }
    assert "sequence" not in response.json()["opening_positions"][0]
    assert len(service.commands) == 1
    assert service.commands[0].positions[0].position_type is None


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (UserNotFound(USER_ID), 404, "USER_NOT_FOUND"),
        (OpeningStateSealed(), 409, "OPENING_STATE_SEALED"),
        (InvalidPortfolioValue("重复仓位"), 422, "INVALID_OPENING_STATE"),
    ],
)
def test_maps_opening_state_errors(
    client: TestClient,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    """Opening State 的未知 User、封闭与非法 Batch 必须保持可区分。"""

    override_service(FakeOpeningPositionService(error))

    response = client.post(
        f"/v1/portfolios/{USER_ID}/opening-positions",
        json={"positions": [{"ticker": "GOOG", "shares": "1", "average_cost": "100"}]},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code


def test_rejects_client_derived_opening_fields_before_service_call(client: TestClient) -> None:
    """Opening Position 不接受 Cost Basis、ID、时间或 sequence 等派生字段。"""

    service = FakeOpeningPositionService((make_opening_position(),))
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/opening-positions",
        json={
            "positions": [
                {
                    "ticker": "GOOG",
                    "shares": "1",
                    "average_cost": "100",
                    "cost_basis": "100",
                    "sequence": 1,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert service.commands == []


def test_returns_complete_read_only_record_lists(client: TestClient) -> None:
    """三个 Record Endpoint 应返回完整性声明与稳定后端事实。"""

    opening_service = FakeOpeningPositionService((make_opening_position(),))
    override_service(opening_service)
    opening_response = client.get(f"/v1/portfolios/{USER_ID}/opening-positions")

    override_service(FakeTransactionListReader((make_transaction(),)))
    transaction_response = client.get(f"/v1/portfolios/{USER_ID}/transactions")

    override_service(FakeCashEventListReader((make_result().cash_event,)))
    cash_response = client.get(f"/v1/portfolios/{USER_ID}/cash-events")

    assert opening_response.status_code == 200
    assert opening_response.json()["items_are_complete"] is True
    assert opening_response.json()["items"][0]["position_type"] == "UNSPECIFIED"
    assert "sequence" not in opening_response.json()["items"][0]
    assert transaction_response.status_code == 200
    assert transaction_response.json()["items"][0]["sequence"] == 1
    assert cash_response.status_code == 200
    assert cash_response.json()["items"][0]["event_type"] == "DEPOSIT"


def test_record_list_endpoints_map_unknown_user_to_404(client: TestClient) -> None:
    """三个完整记录列表必须对未知 User 返回统一 404 Contract。"""

    cases = (
        ("opening-positions", FakeOpeningPositionService(UserNotFound(USER_ID))),
        ("transactions", FakeTransactionListReader(UserNotFound(USER_ID))),
        ("cash-events", FakeCashEventListReader(UserNotFound(USER_ID))),
    )
    for path, service in cases:
        override_service(service)
        response = client.get(f"/v1/portfolios/{USER_ID}/{path}")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "USER_NOT_FOUND"


def test_transaction_position_type_is_optional_and_canonical_in_response(
    client: TestClient,
) -> None:
    """省略 Position Type 时 Command 保留缺省，Response 返回 UNSPECIFIED。"""

    transaction = Transaction.create(
        transaction_id=TRANSACTION_ID,
        user_id=USER_ID,
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("10"),
        shares=Decimal("1"),
        occurred_at=OCCURRED_AT,
    )
    service = FakeTransactionWriter(transaction)
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/transactions",
        json={"ticker": "GOOG", "action": "BUY", "price": "10", "shares": "1"},
    )

    assert response.status_code == 201
    assert response.json()["transaction"]["position_type"] == "UNSPECIFIED"
    assert service.commands[0].position_type is None


def test_records_transaction_and_returns_backend_derived_fields(client: TestClient) -> None:
    """Transaction API 不接收派生字段，并完整返回后端 Ledger Record。"""

    service = FakeTransactionWriter(make_transaction())
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/transactions",
        json={
            "ticker": "goog",
            "action": "BUY",
            "price": "180.25",
            "shares": "2",
            "position_type": "LONG_TERM",
            "reason": "Initial long-term position",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "transaction": {
            "id": str(TRANSACTION_ID),
            "user_id": str(USER_ID),
            "sequence": 1,
            "ticker": "GOOG",
            "action": "BUY",
            "price": "180.25000000",
            "shares": "2.00000000",
            "amount": "360.50000000",
            "commission": "0.35000000",
            "fee_schedule": "IBKR_PRO_TIERED_US_2026_08",
            "position_type": "LONG_TERM",
            "occurred_at": "2026-08-25T08:30:00Z",
            "reason": "Initial long-term position",
        }
    }
    assert len(service.commands) == 1
    command = service.commands[0]
    assert command.user_id == USER_ID
    assert command.ticker == "goog"
    assert command.action is TransactionAction.BUY
    assert command.price == Decimal("180.25")
    assert command.shares == Decimal("2")
    assert command.position_type is PositionType.LONG_TERM
    assert command.occurred_at is None


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (UserNotFound(USER_ID), 404, "USER_NOT_FOUND"),
        (
            InsufficientCash(available=Decimal("10"), required=Decimal("11")),
            409,
            "INSUFFICIENT_CASH",
        ),
        (
            InsufficientShares(available=Decimal("1"), required=Decimal("2")),
            409,
            "INSUFFICIENT_SHARES",
        ),
        (InvalidPortfolioValue("ticker 格式无效"), 422, "INVALID_TRANSACTION"),
    ],
)
def test_maps_transaction_application_errors(
    client: TestClient,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    """Transaction Application Failure 应映射为稳定且可区分的状态。"""

    override_service(FakeTransactionWriter(error))

    response = client.post(
        f"/v1/portfolios/{USER_ID}/transactions",
        json={
            "ticker": "GOOG",
            "action": "SELL",
            "price": "10",
            "shares": "2",
            "position_type": "SWING",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code


@pytest.mark.parametrize(
    "payload",
    [
        {
            "ticker": "GOOG",
            "action": "DIVIDEND",
            "price": "10",
            "shares": "1",
            "position_type": "LONG_TERM",
        },
        {
            "ticker": "GOOG",
            "action": "BUY",
            "price": "0",
            "shares": "1",
            "position_type": "LONG_TERM",
        },
        {
            "ticker": "GOOG",
            "action": "BUY",
            "price": "10",
            "shares": "1.000000001",
            "position_type": "LONG_TERM",
        },
        {
            "ticker": "GOOG",
            "action": "BUY",
            "price": "10",
            "shares": "1",
            "position_type": "DAY_TRADE",
        },
        {
            "ticker": "GOOG",
            "action": "BUY",
            "price": "10",
            "shares": "1",
            "position_type": "LONG_TERM",
            "occurred_at": "2026-08-25T08:30:00",
        },
        {
            "ticker": "GOOG",
            "action": "BUY",
            "price": "10",
            "shares": "1",
            "position_type": "LONG_TERM",
            "amount": "10",
            "commission": "0.35",
            "fee_schedule": "CLIENT_VALUE",
        },
    ],
)
def test_rejects_invalid_transaction_request_before_service_call(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    """非法 Transaction Request 不得进入 Application Service。"""

    service = FakeTransactionWriter(make_transaction())
    override_service(service)

    response = client.post(f"/v1/portfolios/{USER_ID}/transactions", json=payload)

    assert response.status_code == 422
    assert service.commands == []


def test_records_deposit_and_returns_rebuilt_available_cash(client: TestClient) -> None:
    """成功写入应返回 201、不可变事件和重建后的 Available Cash。"""

    service = FakePortfolioService(make_result())
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/cash-events",
        json={
            "event_type": "DEPOSIT",
            "amount": "500",
            "occurred_at": "2026-08-25T16:30:00+08:00",
            "reason": "追加投资预算",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "cash_event": {
            "id": str(EVENT_ID),
            "user_id": str(USER_ID),
            "sequence": 1,
            "event_type": "DEPOSIT",
            "amount": "500.00000000",
            "occurred_at": "2026-08-25T08:30:00Z",
            "reason": "追加投资预算",
        },
        "available_cash": "1500.00000000",
    }
    assert len(service.commands) == 1
    command = service.commands[0]
    assert command.user_id == USER_ID
    assert command.event_type is CashEventType.DEPOSIT
    assert command.amount == Decimal("500")
    assert command.occurred_at is not None
    assert command.occurred_at.utcoffset() is not None


def test_cash_event_allows_application_clock_default(client: TestClient) -> None:
    """Cash Event API 省略时间时不使用 Browser Clock。"""

    service = FakePortfolioService(make_result())
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/cash-events",
        json={"event_type": "DEPOSIT", "amount": "500"},
    )

    assert response.status_code == 201
    assert len(service.commands) == 1
    assert service.commands[0].occurred_at is None


def test_maps_insufficient_cash_to_conflict(client: TestClient) -> None:
    """超额 Withdrawal 应返回稳定 409，而不是写入伪成功。"""

    service = FakePortfolioService(
        InsufficientCash(available=Decimal("100"), required=Decimal("101"))
    )
    override_service(service)

    response = client.post(
        f"/v1/portfolios/{USER_ID}/cash-events",
        json={
            "event_type": "WITHDRAWAL",
            "amount": "101",
            "occurred_at": "2026-08-25T08:30:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "INSUFFICIENT_CASH",
            "message": "可用现金 100 少于所需金额 101",
        }
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (UserNotFound(USER_ID), 404, "USER_NOT_FOUND"),
        (InvalidPortfolioValue("amount 无效"), 422, "INVALID_CASH_EVENT"),
    ],
)
def test_maps_application_errors(
    client: TestClient,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    """未知 User 与领域输入失败应保持不同 API 状态。"""

    override_service(FakePortfolioService(error))

    response = client.post(
        f"/v1/portfolios/{USER_ID}/cash-events",
        json={
            "event_type": "DEPOSIT",
            "amount": "1",
            "occurred_at": "2026-08-25T08:30:00Z",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code


@pytest.mark.parametrize(
    "payload",
    [
        {"event_type": "DIVIDEND", "amount": "1", "occurred_at": "2026-08-25T08:30:00Z"},
        {"event_type": "DEPOSIT", "amount": "0", "occurred_at": "2026-08-25T08:30:00Z"},
        {
            "event_type": "DEPOSIT",
            "amount": "1.000000001",
            "occurred_at": "2026-08-25T08:30:00Z",
        },
        {"event_type": "DEPOSIT", "amount": "1", "occurred_at": "2026-08-25T08:30:00"},
    ],
)
def test_rejects_invalid_request_before_service_call(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    """非法类型、金额或时间不得进入 Application Service。"""

    service = FakePortfolioService(make_result())
    override_service(service)

    response = client.post(f"/v1/portfolios/{USER_ID}/cash-events", json=payload)

    assert response.status_code == 422
    assert service.commands == []
