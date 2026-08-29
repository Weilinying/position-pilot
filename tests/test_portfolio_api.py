"""M4 Cash Adjustment API Contract 测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from position_pilot.application.errors import UserNotFound
from position_pilot.application.portfolio_service import (
    CashAdjustmentResult,
    RecordCashEventCommand,
)
from position_pilot.domain.errors import InsufficientCash, InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    CashBalance,
    CashEvent,
    CashEventType,
    PortfolioState,
    Position,
    PositionType,
    User,
    rebuild_portfolio,
)
from position_pilot.main import app, get_portfolio_service_dependency

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000002")
OCCURRED_AT = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)


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
class FakePortfolioReader:
    """返回固定 Portfolio State，并记录只读查询。"""

    result: PortfolioState | Exception
    user_ids: list[UUID] = field(default_factory=list)

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        self.user_ids.append(user_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试后恢复 Cash Adjustment Dependency Override。"""

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


def override_service(service: FakePortfolioService | FakePortfolioReader) -> None:
    """避免 API Contract Test 读取真实数据库。"""

    app.dependency_overrides[get_portfolio_service_dependency] = lambda: service


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
    assert command.occurred_at.utcoffset() is not None


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
        {"event_type": "DEPOSIT", "amount": "1"},
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
