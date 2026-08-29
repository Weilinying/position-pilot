"""为 M7 本地演示创建隔离 Portfolio 的显式命令。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from position_pilot.application.portfolio_service import (
    CreateUserCommand,
    RecordTransactionCommand,
)
from position_pilot.bootstrap import get_portfolio_service
from position_pilot.domain.portfolio import PositionType, Transaction, TransactionAction, User


class DemoPortfolioWriter(Protocol):
    """Demo Seed 所需的最小 Application Service 接口。"""

    def create_user(self, command: CreateUserCommand) -> User: ...

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction: ...


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    """成功创建的隔离 Demo Portfolio 身份。"""

    user_id: UUID
    transaction_count: int


@dataclass(frozen=True, slots=True)
class DemoTransactionFixture:
    """单条 Demo BUY 的明确类型输入。"""

    ticker: str
    price: Decimal
    shares: Decimal
    position_type: PositionType
    occurred_at: datetime
    reason: str


DEMO_TRANSACTIONS = (
    DemoTransactionFixture(
        ticker="GOOG",
        price=Decimal("180"),
        shares=Decimal("10"),
        position_type=PositionType.LONG_TERM,
        occurred_at=datetime(2026, 6, 12, 14, 30, tzinfo=UTC),
        reason="Demo 长期核心仓",
    ),
    DemoTransactionFixture(
        ticker="GOOG",
        price=Decimal("210"),
        shares=Decimal("4"),
        position_type=PositionType.SWING,
        occurred_at=datetime(2026, 7, 17, 14, 30, tzinfo=UTC),
        reason="Demo 波段计划仓",
    ),
    DemoTransactionFixture(
        ticker="NVDA",
        price=Decimal("140"),
        shares=Decimal("8"),
        position_type=PositionType.LONG_TERM,
        occurred_at=datetime(2026, 8, 8, 14, 30, tzinfo=UTC),
        reason="Demo 第二长期持仓",
    ),
)


def seed_demo_portfolio(service: DemoPortfolioWriter) -> DemoSeedResult:
    """通过正式 Application Service 创建新的隔离 Demo Ledger。"""

    user = service.create_user(
        CreateUserCommand(
            display_name="PositionPilot Demo",
            initial_cash=Decimal("15000"),
        )
    )
    for fixture in DEMO_TRANSACTIONS:
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker=fixture.ticker,
                action=TransactionAction.BUY,
                price=fixture.price,
                shares=fixture.shares,
                position_type=fixture.position_type,
                occurred_at=fixture.occurred_at,
                reason=fixture.reason,
            )
        )
    return DemoSeedResult(user_id=user.id, transaction_count=len(DEMO_TRANSACTIONS))


def main() -> None:
    """创建 Demo Portfolio 并只输出非敏感本地访问资料。"""

    result = seed_demo_portfolio(get_portfolio_service())
    print(f"Demo Portfolio User ID: {result.user_id}")
    print(f"Transactions: {result.transaction_count}")
    print(f"Open: http://127.0.0.1:8000/app/?user_id={result.user_id}")


if __name__ == "__main__":
    main()
