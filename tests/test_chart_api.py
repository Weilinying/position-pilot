"""Portfolio Chart API 的 Session、访问边界与序列化测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import Account
from position_pilot.application.portfolio_chart_service import (
    ChartAssetNotFound,
    ChartRange,
    ChartSellAllocation,
    ChartTransaction,
    ChartTransactionMarker,
    PortfolioChart,
)
from position_pilot.domain.market_data import MarketDataCoverage, MarketDataStatus, OHLCVBar
from position_pilot.domain.portfolio import PositionType, TransactionAction
from position_pilot.main import (
    app,
    get_current_account_dependency,
    get_portfolio_chart_service_dependency,
)

NOW = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)
USER_ID = UUID("00000000-0000-0000-0000-000000000013")


def make_account(*, ready: bool = True) -> Account:
    return Account(
        id=UUID(int=1),
        email="chart@example.test",
        display_name="Chart",
        password_hash="fixture",
        portfolio_user_id=USER_ID if ready else None,
        created_at=NOW,
    )


def make_chart() -> PortfolioChart:
    buy_id = UUID("00000000-0000-0000-0000-000000000101")
    sell_id = UUID("00000000-0000-0000-0000-000000000102")
    lot_id = UUID("00000000-0000-0000-0000-000000000103")
    buy = ChartTransaction(
        transaction_id=buy_id,
        action=TransactionAction.BUY,
        occurred_at=datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
        market_date=date(2026, 9, 10),
        shares=Decimal("4"),
        price=Decimal("100"),
        fee=Decimal("0"),
        fee_schedule="BUY_COST_INCLUDED",
        position_type=PositionType.SWING,
        allocations=(),
    )
    sell = ChartTransaction(
        transaction_id=sell_id,
        action=TransactionAction.SELL,
        occurred_at=datetime(2026, 9, 11, 15, 0, tzinfo=UTC),
        market_date=date(2026, 9, 11),
        shares=Decimal("2"),
        price=Decimal("120"),
        fee=Decimal("1"),
        fee_schedule="SELL_ACTUAL_FEE",
        position_type=PositionType.UNSPECIFIED,
        allocations=(
            ChartSellAllocation(
                lot_id=lot_id,
                source="BUY",
                shares=Decimal("2"),
                position_type_at_sale=PositionType.SWING,
                allocated_gross_proceeds=Decimal("240"),
                allocated_fee=Decimal("1"),
                allocated_net_proceeds=Decimal("239"),
                released_cost=Decimal("200"),
                realized_pnl=Decimal("39"),
            ),
        ),
    )
    return PortfolioChart(
        user_id=USER_ID,
        ticker="GOOG",
        chart_range=ChartRange.THREE_MONTHS,
        anchor_date=date(2026, 9, 15),
        requested_start=date(2026, 6, 15),
        requested_end=date(2026, 9, 15),
        timeframe="1Day",
        status=MarketDataStatus.OK,
        message=None,
        bars=(
            OHLCVBar(
                timestamp=datetime(2026, 9, 10, 4, 0, tzinfo=UTC),
                open=Decimal("100"),
                high=Decimal("125"),
                low=Decimal("95"),
                close=Decimal("120"),
                volume=1000,
            ),
        ),
        source="ALPACA",
        feed="SIP",
        coverage=MarketDataCoverage.CONSOLIDATED,
        currency="USD",
        adjustment="ALL",
        fetched_at=NOW,
        current_cost=None,
        cost_basis_comparable=False,
        cost_line_unavailable_reason="NO_CURRENT_POSITION",
        markers=(
            ChartTransactionMarker(
                market_date=date(2026, 9, 10),
                has_bar=True,
                transactions=(buy,),
            ),
            ChartTransactionMarker(
                market_date=date(2026, 9, 11),
                has_bar=False,
                transactions=(sell,),
            ),
        ),
    )


@dataclass(slots=True)
class FakeChartService:
    """记录 Session 传入的用户并返回固定结果。"""

    result: PortfolioChart | Exception
    requests: list[tuple[UUID, str, ChartRange, date | None]] = field(default_factory=list)

    def get_chart(
        self,
        user_id: UUID,
        ticker: str,
        chart_range: ChartRange,
        *,
        anchor_date: date | None,
    ) -> PortfolioChart:
        self.requests.append((user_id, ticker, chart_range, anchor_date))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_account_dependency] = make_account
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_chart_api_serializes_nested_markers_and_decimal_values(client: TestClient) -> None:
    service = FakeChartService(make_chart())
    app.dependency_overrides[get_portfolio_chart_service_dependency] = lambda: service
    response = client.get(
        "/v1/portfolio/chart",
        params={"ticker": "GOOG", "range": "3M", "anchor_date": "2026-09-15"},
    )
    assert response.status_code == 200
    body = response.json()
    assert service.requests == [(USER_ID, "GOOG", ChartRange.THREE_MONTHS, date(2026, 9, 15))]
    assert body["timeframe"] == "1Day"
    assert body["adjustment"] == "ALL"
    assert body["bars"][0]["close"] == "120"
    assert body["markers"][1]["has_bar"] is False
    assert body["markers"][1]["transactions"][0]["action"] == "SELL"
    assert (
        body["markers"][1]["transactions"][0]["allocations"][0]["allocated_net_proceeds"] == "239"
    )


def test_chart_api_maps_unowned_asset_to_404_without_provider_access(client: TestClient) -> None:
    service = FakeChartService(ChartAssetNotFound("AAPL"))
    app.dependency_overrides[get_portfolio_chart_service_dependency] = lambda: service
    response = client.get("/v1/portfolio/chart", params={"ticker": "AAPL", "range": "3M"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CHART_ASSET_NOT_FOUND"


@pytest.mark.parametrize("status_code", [401, 409])
def test_chart_api_preserves_session_boundaries(client: TestClient, status_code: int) -> None:
    service = FakeChartService(make_chart())
    app.dependency_overrides[get_portfolio_chart_service_dependency] = lambda: service
    if status_code == 401:

        def anonymous() -> Account:
            raise HTTPException(status_code=401)

        app.dependency_overrides[get_current_account_dependency] = anonymous
    else:
        app.dependency_overrides[get_current_account_dependency] = lambda: make_account(ready=False)
    response = client.get("/v1/portfolio/chart", params={"ticker": "GOOG", "range": "3M"})
    assert response.status_code == status_code
    assert service.requests == []
