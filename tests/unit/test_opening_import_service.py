"""已确认 Opening State Import Application 编排测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from position_pilot.application.auth_service import SetupPortfolioCommand
from position_pilot.application.opening_import_service import OpeningImportService
from position_pilot.application.portfolio_service import (
    InitializeOpeningPositionsCommand,
    OpeningPositionInput,
)
from position_pilot.domain.portfolio import OpeningPosition, PositionType, User

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
ACCOUNT_ID = UUID("00000000-0000-4000-8000-000000000001")
USER_ID = UUID("00000000-0000-4000-8000-000000000002")


@dataclass(slots=True)
class FakeAuthService:
    """记录本地 Browser Confirm 的 Portfolio Setup。"""

    result: User
    commands: list[SetupPortfolioCommand] = field(default_factory=list)

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        self.commands.append(command)
        return self.result


@dataclass(slots=True)
class FakePortfolioService:
    """记录本地 Browser Confirm 的 Existing State 初始化。"""

    result: tuple[OpeningPosition, ...] = ()
    commands: list[InitializeOpeningPositionsCommand] = field(default_factory=list)

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        self.commands.append(command)
        return self.result


def make_user() -> User:
    """创建 Setup Portfolio 的固定返回值。"""

    return User.create(
        user_id=USER_ID,
        display_name="Local Investor",
        initial_cash=Decimal("1000"),
        created_at=NOW,
    )


def make_position(symbol: str = "GOOG") -> OpeningPositionInput:
    """创建 Browser 已绑定 canonical symbol 的测试字段。"""

    return OpeningPositionInput(
        ticker=symbol,
        shares=Decimal("2"),
        average_cost=Decimal("100"),
        position_type=PositionType.LONG_TERM,
    )


def test_setup_forwards_confirmed_browser_draft_without_provider_call() -> None:
    """Confirm 直接进入原子 Setup，不再依赖 Asset Provider。"""

    auth = FakeAuthService(make_user())
    portfolio = FakePortfolioService()
    service = OpeningImportService(auth, portfolio)
    command = SetupPortfolioCommand(
        account_id=ACCOUNT_ID,
        initial_cash=Decimal("1000"),
        opening_positions=(make_position(),),
    )

    result = service.setup_portfolio(command)

    assert result == auth.result
    assert auth.commands == [command]
    assert portfolio.commands == []


def test_existing_portfolio_forwards_confirmed_draft_to_atomic_writer() -> None:
    """Existing Portfolio Confirm 保留 PortfolioService 的 Gate 与原子写入边界。"""

    auth = FakeAuthService(make_user())
    portfolio = FakePortfolioService()
    service = OpeningImportService(auth, portfolio)
    command = InitializeOpeningPositionsCommand(
        user_id=USER_ID,
        positions=(make_position("NVDA"),),
    )

    result = service.initialize_opening_positions(command)

    assert result == ()
    assert portfolio.commands == [command]
    assert auth.commands == []
