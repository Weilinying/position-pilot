"""M7 Demo Portfolio Seed 测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot import demo_seed
from position_pilot.application.portfolio_service import (
    CreateUserCommand,
    RecordTransactionCommand,
)
from position_pilot.domain.portfolio import PositionType, Transaction, User

USER_ID = UUID("40000000-0000-4000-8000-000000000004")


@dataclass(slots=True)
class FakeDemoPortfolioWriter:
    """记录 Seed Commands，并返回满足领域约束的实体。"""

    create_commands: list[CreateUserCommand] = field(default_factory=list)
    transaction_commands: list[RecordTransactionCommand] = field(default_factory=list)

    def create_user(self, command: CreateUserCommand) -> User:
        self.create_commands.append(command)
        return User.create(
            user_id=USER_ID,
            display_name=command.display_name,
            initial_cash=command.initial_cash,
            created_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
        )

    def record_transaction(self, command: RecordTransactionCommand) -> Transaction:
        self.transaction_commands.append(command)
        return Transaction.create(
            transaction_id=UUID(int=len(self.transaction_commands)),
            user_id=command.user_id,
            sequence=len(self.transaction_commands),
            ticker=command.ticker,
            action=command.action,
            price=command.price,
            shares=command.shares,
            position_type=command.position_type,
            occurred_at=command.occurred_at,
            reason=command.reason,
        )


def test_seed_uses_application_commands_and_preserves_position_types() -> None:
    """Seed 不得绕过正式 User / Transaction Use Case。"""

    service = FakeDemoPortfolioWriter()

    result = demo_seed.seed_demo_portfolio(service)

    assert result.user_id == USER_ID
    assert result.transaction_count == 3
    assert service.create_commands == [
        CreateUserCommand(display_name="PositionPilot Demo", initial_cash=Decimal("15000"))
    ]
    assert [
        (command.ticker, command.position_type) for command in service.transaction_commands
    ] == [
        ("GOOG", PositionType.LONG_TERM),
        ("GOOG", PositionType.SWING),
        ("NVDA", PositionType.LONG_TERM),
    ]
    assert all(command.user_id == USER_ID for command in service.transaction_commands)


def test_main_prints_only_demo_identity_and_local_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 输出应足以启动 Demo，且不包含 Credential。"""

    service = FakeDemoPortfolioWriter()
    monkeypatch.setattr(demo_seed, "get_portfolio_service", lambda: service)

    demo_seed.main()

    output = capsys.readouterr().out
    assert f"Demo Portfolio User ID: {USER_ID}" in output
    assert f"http://127.0.0.1:8000/app/?user_id={USER_ID}" in output
    assert "secret" not in output.lower()
