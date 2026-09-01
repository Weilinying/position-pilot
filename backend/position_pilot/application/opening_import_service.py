"""已确认 Opening State Import 的 Application 编排。"""

from collections.abc import Sequence
from typing import Protocol

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.auth_service import AuthService, SetupPortfolioCommand
from position_pilot.application.errors import ApplicationError
from position_pilot.application.portfolio_service import (
    InitializeOpeningPositionsCommand,
    OpeningPositionInput,
    PortfolioService,
)
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetStatus,
    AssetValidationResult,
)
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import OpeningPosition, PositionType, User


class AssetMetadataValidationError(ApplicationError):
    """Opening Import 的 Asset Validation Failure，保留稳定 Provider-neutral 状态。"""

    def __init__(
        self,
        *,
        symbol: str,
        status: AssetMetadataStatus,
        message: str,
        asset_status: AssetStatus | None = None,
    ) -> None:
        self.symbol = symbol
        self.status = status
        self.asset_metadata_status = status
        self.asset_status = asset_status
        self.message = message
        super().__init__(f"Asset '{symbol}' validation failed: {status.value} - {message}")


class AssetMetadataValidator(Protocol):
    """AssetMetadataService 提供给 Opening Import 的最小验证边界。"""

    def validate(self, symbol: str) -> AssetValidationResult: ...


class PortfolioSetupWriter(Protocol):
    """AuthService 提供给 Opening Import 的 Portfolio Setup 边界。"""

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User: ...


class OpeningStateWriter(Protocol):
    """PortfolioService 提供给 Opening Import 的 Existing State 写入边界。"""

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]: ...


class OpeningImportService:
    """编排已确认字段的 Asset Validation 与一次性 Opening State 写入。

    `AssetMetadataService`、`AuthService` 与 `PortfolioService` 分别负责 Provider-neutral
    Asset 验证、Portfolio Setup 和既有 Portfolio 的 Opening State 写入。本服务只在这些
    边界之间传递已确认字段，不持久化 Draft，也不引入额外 Domain 或 Database 状态。
    """

    def __init__(
        self,
        asset_metadata_service: AssetMetadataService | AssetMetadataValidator,
        auth_service: AuthService | PortfolioSetupWriter,
        portfolio_service: PortfolioService | OpeningStateWriter,
    ) -> None:
        self._asset_metadata_service = asset_metadata_service
        self._auth_service = auth_service
        self._portfolio_service = portfolio_service

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        """确认并创建 Account 的唯一 Portfolio 与可选 Opening State。

        Asset Provider 验证在调用 `AuthService` 前完成；没有 Opening Positions 时不调用
        Provider，保留纯现金 Portfolio Setup 的既有路径。
        """

        validated_positions = self._validated_positions(command.opening_positions)
        validated_command = SetupPortfolioCommand(
            account_id=command.account_id,
            initial_cash=command.initial_cash,
            opening_positions=validated_positions,
        )
        return self._auth_service.setup_portfolio(validated_command)

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        """确认并初始化仍处于 Opening State 阶段的 Existing Portfolio 仓位。"""

        validated_positions = self._validated_positions(command.positions)
        validated_command = InitializeOpeningPositionsCommand(
            user_id=command.user_id,
            positions=validated_positions,
        )
        return self._portfolio_service.initialize_opening_positions(validated_command)

    def _validated_positions(
        self,
        positions: Sequence[OpeningPositionInput],
    ) -> tuple[OpeningPositionInput, ...]:
        """在任何写服务打开事务前验证并转换全部 Position Symbol。"""

        if not positions:
            return ()

        validated: list[OpeningPositionInput] = []
        seen_keys: set[tuple[str, PositionType]] = set()
        for position in positions:
            asset = self._validate_asset(position.ticker)
            position_type = position.position_type or PositionType.UNSPECIFIED
            key = (asset.canonical_symbol, position_type)
            if key in seen_keys:
                raise InvalidPortfolioValue(
                    "opening_positions 不能包含重复的 canonical_symbol 与 position_type"
                )
            seen_keys.add(key)
            validated.append(
                OpeningPositionInput(
                    ticker=asset.canonical_symbol,
                    shares=position.shares,
                    average_cost=position.average_cost,
                    position_type=position.position_type,
                )
            )
        return tuple(validated)

    def _validate_asset(self, symbol: str) -> AssetIdentity:
        """执行单行 exact validation，并拒绝非 active 或 Provider Failure。"""

        try:
            result = self._asset_metadata_service.validate(symbol)
        except Exception as error:
            # Provider Adapter 正常应返回结构化 Failure；异常也必须阻止写入。
            raise AssetMetadataValidationError(
                symbol=symbol,
                status=AssetMetadataStatus.PROVIDER_UNAVAILABLE,
                message="Asset Metadata Provider 不可用",
            ) from error

        if result.status is not AssetMetadataStatus.OK:
            raise AssetMetadataValidationError(
                symbol=symbol,
                status=result.status,
                message=result.message or "Asset Metadata validation 失败",
            )
        if result.asset is None:
            raise AssetMetadataValidationError(
                symbol=symbol,
                status=AssetMetadataStatus.INVALID_PROVIDER_RESPONSE,
                message="Asset Metadata validation 未返回 Asset",
            )
        if result.asset.status is not AssetStatus.ACTIVE:
            raise AssetMetadataValidationError(
                symbol=symbol,
                status=AssetMetadataStatus.NO_MATCH,
                message="Asset 当前不可用于 Opening State",
                asset_status=result.asset.status,
            )
        return result.asset


__all__ = [
    "AssetMetadataValidationError",
    "OpeningImportService",
]
