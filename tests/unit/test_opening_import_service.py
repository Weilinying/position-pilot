"""已确认 Opening State Import Application 编排测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.auth_service import SetupPortfolioCommand
from position_pilot.application.opening_import_service import (
    AssetMetadataValidationError,
    OpeningImportService,
)
from position_pilot.application.portfolio_service import (
    InitializeOpeningPositionsCommand,
    OpeningPositionInput,
)
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetStatus,
    AssetValidationResult,
)
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import OpeningPosition, PositionType, User

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
ACCOUNT_ID = UUID("00000000-0000-4000-8000-000000000001")
USER_ID = UUID("00000000-0000-4000-8000-000000000002")


def identity(
    symbol: str,
    *,
    name: str = "Example Asset",
    status: AssetStatus = AssetStatus.ACTIVE,
) -> AssetIdentity:
    """创建最小 Provider-neutral Asset Identity。"""

    return AssetIdentity(
        canonical_symbol=symbol,
        display_name=name,
        exchange="NASDAQ",
        status=status,
    )


@dataclass(slots=True)
class FakeAssetMetadataService:
    """记录 exact validation 顺序并返回固定结果。"""

    results: dict[str, AssetValidationResult | Exception]
    calls: list[str] = field(default_factory=list)
    events: list[str] | None = None

    def validate(self, symbol: str) -> AssetValidationResult:
        self.calls.append(symbol)
        if self.events is not None:
            self.events.append(f"validate:{symbol}")
        result = self.results[symbol]
        if isinstance(result, Exception):
            raise result
        return result


@dataclass(slots=True)
class FakeAuthService:
    """记录 AuthService Portfolio Setup 调用。"""

    result: User
    commands: list[SetupPortfolioCommand] = field(default_factory=list)
    events: list[str] | None = None

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        if self.events is not None:
            self.events.append("setup")
        self.commands.append(command)
        return self.result


@dataclass(slots=True)
class FakePortfolioService:
    """记录 Existing Portfolio Opening State 初始化调用。"""

    result: tuple[OpeningPosition, ...] = ()
    commands: list[InitializeOpeningPositionsCommand] = field(default_factory=list)
    events: list[str] | None = None

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        if self.events is not None:
            self.events.append("initialize")
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


def make_position(
    symbol: str,
    *,
    position_type: PositionType | None = None,
) -> OpeningPositionInput:
    """创建测试使用的已确认 Opening Position 字段。"""

    return OpeningPositionInput(
        ticker=symbol,
        shares=Decimal("2"),
        average_cost=Decimal("100"),
        position_type=position_type,
    )


def make_service(
    asset_metadata: FakeAssetMetadataService,
    auth: FakeAuthService | None = None,
    portfolio: FakePortfolioService | None = None,
) -> OpeningImportService:
    """组装只使用 Provider-neutral 边界的测试 Service。"""

    return OpeningImportService(
        asset_metadata,
        auth or FakeAuthService(make_user()),
        portfolio or FakePortfolioService(),
    )


def test_setup_validates_all_assets_before_auth_write_and_uses_canonical_symbols() -> None:
    """全部 exact validation 成功后，Setup 才能收到 Provider canonical symbol。"""

    events: list[str] = []
    metadata = FakeAssetMetadataService(
        results={
            " goog ": AssetValidationResult.success(identity("GOOG", name="Alphabet Inc.")),
            "spy": AssetValidationResult.success(identity("SPY", name="SPDR S&P 500")),
        },
        events=events,
    )
    auth = FakeAuthService(make_user(), events=events)
    service = make_service(metadata, auth=auth)

    service.setup_portfolio(
        SetupPortfolioCommand(
            account_id=ACCOUNT_ID,
            initial_cash=Decimal("1000"),
            opening_positions=(make_position(" goog "), make_position("spy")),
        )
    )

    assert events == ["validate: goog ", "validate:spy", "setup"]
    assert len(auth.commands) == 1
    assert [position.ticker for position in auth.commands[0].opening_positions] == [
        "GOOG",
        "SPY",
    ]


def test_existing_portfolio_validates_before_initialize_write() -> None:
    """Existing Portfolio 初始化必须复用 PortfolioService 的原子写入边界。"""

    events: list[str] = []
    metadata = FakeAssetMetadataService(
        results={"nvda": AssetValidationResult.success(identity("NVDA"))},
        events=events,
    )
    portfolio = FakePortfolioService(events=events)
    service = make_service(metadata, portfolio=portfolio)

    service.initialize_opening_positions(
        InitializeOpeningPositionsCommand(
            user_id=USER_ID,
            positions=(make_position("nvda", position_type=PositionType.SWING),),
        )
    )

    assert events == ["validate:nvda", "initialize"]
    assert portfolio.commands[0].user_id == USER_ID
    assert portfolio.commands[0].positions[0] == OpeningPositionInput(
        ticker="NVDA",
        shares=Decimal("2"),
        average_cost=Decimal("100"),
        position_type=PositionType.SWING,
    )


def test_empty_setup_skips_asset_provider() -> None:
    """没有 Opening Positions 的纯现金 Setup 不应调用 Asset Provider。"""

    metadata = FakeAssetMetadataService(results={})
    auth = FakeAuthService(make_user())
    service = make_service(metadata, auth=auth)

    service.setup_portfolio(
        SetupPortfolioCommand(
            account_id=ACCOUNT_ID,
            initial_cash=Decimal("1000"),
            opening_positions=(),
        )
    )

    assert metadata.calls == []
    assert auth.commands[0].opening_positions == ()


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [
        (
            AssetValidationResult.failure(AssetMetadataStatus.NO_MATCH, "没有匹配 Asset"),
            AssetMetadataStatus.NO_MATCH,
        ),
        (
            AssetValidationResult.failure(
                AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                "Provider 暂时不可用",
            ),
            AssetMetadataStatus.PROVIDER_UNAVAILABLE,
        ),
        (
            AssetValidationResult.success(identity("DEAD", status=AssetStatus.INACTIVE)),
            AssetMetadataStatus.NO_MATCH,
        ),
    ],
)
def test_asset_failure_exposes_stable_status_and_never_writes(
    result: AssetValidationResult,
    expected_status: AssetMetadataStatus,
) -> None:
    """No Match、Inactive 与 Provider Failure 都必须在写入前终止。"""

    metadata = FakeAssetMetadataService(results={"dead": result})
    auth = FakeAuthService(make_user())
    service = make_service(metadata, auth=auth)

    with pytest.raises(AssetMetadataValidationError) as captured:
        service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=ACCOUNT_ID,
                initial_cash=Decimal("1000"),
                opening_positions=(make_position("dead"),),
            )
        )

    assert captured.value.status is expected_status
    assert captured.value.asset_metadata_status is expected_status
    assert auth.commands == []


def test_provider_exception_maps_to_stable_unavailable_status_without_write() -> None:
    """意外 Provider 异常也不能绕过 Asset Validation。"""

    metadata = FakeAssetMetadataService(results={"goog": RuntimeError("credential must not leak")})
    auth = FakeAuthService(make_user())
    service = make_service(metadata, auth=auth)

    with pytest.raises(AssetMetadataValidationError) as captured:
        service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=ACCOUNT_ID,
                initial_cash=Decimal("1000"),
                opening_positions=(make_position("goog"),),
            )
        )

    assert captured.value.status is AssetMetadataStatus.PROVIDER_UNAVAILABLE
    assert "credential must not leak" not in str(captured.value)
    assert auth.commands == []


def test_duplicate_canonical_symbol_and_position_type_is_rejected_before_write() -> None:
    """Provider canonical 化后重复的 Position Key 必须确定性拒绝。"""

    metadata = FakeAssetMetadataService(
        results={
            "alias-one": AssetValidationResult.success(identity("GOOG")),
            "alias-two": AssetValidationResult.success(identity("GOOG")),
        }
    )
    auth = FakeAuthService(make_user())
    service = make_service(metadata, auth=auth)

    with pytest.raises(InvalidPortfolioValue, match="canonical_symbol"):
        service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=ACCOUNT_ID,
                initial_cash=Decimal("1000"),
                opening_positions=(
                    make_position("alias-one"),
                    make_position("alias-two", position_type=PositionType.UNSPECIFIED),
                ),
            )
        )

    assert metadata.calls == ["alias-one", "alias-two"]
    assert auth.commands == []


def test_same_canonical_symbol_with_distinct_position_types_is_allowed() -> None:
    """LONG_TERM 与 SWING 仍可在同一 Ticker 下独立初始化。"""

    metadata = FakeAssetMetadataService(
        results={
            "long": AssetValidationResult.success(identity("GOOG")),
            "swing": AssetValidationResult.success(identity("GOOG")),
        }
    )
    auth = FakeAuthService(make_user())
    service = make_service(metadata, auth=auth)

    service.setup_portfolio(
        SetupPortfolioCommand(
            account_id=ACCOUNT_ID,
            initial_cash=Decimal("1000"),
            opening_positions=(
                make_position("long", position_type=PositionType.LONG_TERM),
                make_position("swing", position_type=PositionType.SWING),
            ),
        )
    )

    assert [position.ticker for position in auth.commands[0].opening_positions] == [
        "GOOG",
        "GOOG",
    ]
