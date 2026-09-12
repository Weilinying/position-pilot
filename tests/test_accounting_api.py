"""M11 核算与首页聚合接口的身份、金额序列化和职责测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import Account
from position_pilot.application.errors import UserNotFound
from position_pilot.domain.portfolio import (
    LotAllocation,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    replay_portfolio,
)
from position_pilot.domain.portfolio_accounting import (
    PortfolioAccounting,
    calculate_portfolio_accounting,
)
from position_pilot.domain.portfolio_summary import PortfolioSummary, summarize_portfolio
from position_pilot.domain.portfolio_valuation import PortfolioValuation
from position_pilot.main import (
    app,
    get_current_account_dependency,
    get_portfolio_service_dependency,
    get_portfolio_summary_service_dependency,
    get_portfolio_valuation_service_dependency,
)

NOW = datetime(2026, 9, 12, tzinfo=UTC)
USER_ID = UUID("00000000-0000-0000-0000-000000000011")


def make_summary() -> PortfolioSummary:
    """完全卖出的真实账本，无需行情即可验证审计字段。"""

    user = User.create(
        user_id=USER_ID, display_name="API", initial_cash=Decimal("1000"), created_at=NOW
    )
    buy = Transaction.create(
        user_id=user.id,
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("100"),
        shares=Decimal("4"),
        position_type=PositionType.SWING,
        occurred_at=NOW,
    )
    sell = Transaction.create(
        user_id=user.id,
        sequence=2,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price=Decimal("120"),
        shares=Decimal("4"),
        fee=Decimal("1"),
        occurred_at=NOW,
    )
    allocation = LotAllocation.create(
        user_id=user.id, sell_transaction_id=sell.id, lot_id=buy.id, shares=Decimal("4")
    )
    replay = replay_portfolio(user, [buy, sell], lot_allocations=[allocation])
    return summarize_portfolio(
        replay.portfolio,
        calculate_portfolio_accounting(replay),
        PortfolioValuation(user_id=user.id, tickers=()),
    )


@dataclass
class FakeAccountingReader:
    """记录 Session 选定的用户并提供固定核算结果。"""

    result: PortfolioAccounting | UserNotFound
    requests: list[UUID] = field(default_factory=list)

    def get_accounting(self, user_id: UUID) -> PortfolioAccounting:
        self.requests.append(user_id)
        if isinstance(self.result, UserNotFound):
            raise self.result
        return self.result


@dataclass
class FakeSummaryReader:
    """首页响应复用完整领域结果。"""

    result: PortfolioSummary | UserNotFound
    requests: list[UUID] = field(default_factory=list)

    def get_summary(self, user_id: UUID) -> PortfolioSummary:
        self.requests.append(user_id)
        if isinstance(self.result, UserNotFound):
            raise self.result
        return self.result


def make_account(*, ready: bool = True) -> Account:
    """只提供身份事实，不读取本地 Session 或配置。"""

    return Account(
        id=UUID(int=1),
        email="m11@example.test",
        display_name="M11",
        password_hash="fixture",
        portfolio_user_id=USER_ID if ready else None,
        created_at=NOW,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    """隔离依赖替换，核算接口不得访问行情依赖。"""

    app.dependency_overrides[get_current_account_dependency] = make_account
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_accounting_is_realized_only_and_serializes_allocation_audit(client: TestClient) -> None:
    """只读核算没有行情，用户不能通过参数选择其他账户。"""

    reader = FakeAccountingReader(make_summary().accounting)
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: reader

    def no_valuation() -> None:
        raise AssertionError("accounting 不应访问行情服务")

    app.dependency_overrides[get_portfolio_valuation_service_dependency] = no_valuation
    response = client.get("/v1/portfolio/accounting", params={"user_id": str(UUID(int=99))})
    assert response.status_code == 200
    body = response.json()
    assert reader.requests == [USER_ID]
    assert set(body) == {"user_id", "metrics", "transactions", "tickers"}
    assert body["metrics"]["realized_pnl"] == "79.00000000"
    item = body["transactions"][0]["allocations"][0]
    assert item["allocated_gross_proceeds"] == "480.00000000"
    assert item["allocated_fee"] == "1.00000000"
    assert item["allocated_net_proceeds"] == "479.00000000"
    assert item["released_cost"] == "400.00000000"
    assert item["position_type_at_sale"] == "SWING"


def test_summary_combines_independent_sections_and_closed_ticker(client: TestClient) -> None:
    """已清仓股票仍在收益摘要里，当前持仓为空。"""

    reader = FakeSummaryReader(make_summary())
    app.dependency_overrides[get_portfolio_summary_service_dependency] = lambda: reader
    response = client.get("/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert reader.requests == [USER_ID]
    assert body["portfolio"]["lots"] == []
    assert body["valuation"]["tickers"] == []
    assert body["tickers"][0]["ticker"] == "GOOG"
    assert body["totals"]["unrealized_pnl"] == "0E-8"
    assert body["totals"]["total_pnl"] == "79.00000000"
    assert body["has_reconciliations"] is False


@pytest.mark.parametrize("endpoint", ["accounting", "summary"])
@pytest.mark.parametrize("failure", ["unauthenticated", "not_ready", "missing_user"])
def test_accounting_read_boundaries(client: TestClient, endpoint: str, failure: str) -> None:
    """未登录、未初始化及用户不存在时保持既有错误语义。"""

    accounting = FakeAccountingReader(UserNotFound(USER_ID))
    summary = FakeSummaryReader(UserNotFound(USER_ID))
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: accounting
    app.dependency_overrides[get_portfolio_summary_service_dependency] = lambda: summary
    if failure == "unauthenticated":

        def unauthenticated() -> Account:
            raise HTTPException(status_code=401)

        app.dependency_overrides[get_current_account_dependency] = unauthenticated
    elif failure == "not_ready":
        app.dependency_overrides[get_current_account_dependency] = lambda: make_account(ready=False)
    response = client.get(f"/v1/portfolio/{endpoint}")
    assert (
        response.status_code
        == {"unauthenticated": 401, "not_ready": 409, "missing_user": 404}[failure]
    )
    if failure != "missing_user":
        assert accounting.requests == []
        assert summary.requests == []
