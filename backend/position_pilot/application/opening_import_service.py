"""已确认 Opening State Import 的 Application 编排。"""

from typing import Protocol

from position_pilot.application.auth_service import AuthService, SetupPortfolioCommand
from position_pilot.application.portfolio_service import (
    InitializeOpeningPositionsCommand,
    PortfolioService,
)
from position_pilot.domain.portfolio import OpeningPosition, User


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
    """把 Browser 已绑定的 canonical symbol 交给确定性 Opening State 写服务。

    M9 接受本地受信任 Browser 边界：Asset Provider 只在候选选择或 Recognition 自动解析时
    调用，Confirm 不重复访问 Provider。底层 AuthService / PortfolioService 仍负责 ticker 格式、
    Decimal、重复 Position、一次性 Gate、Ledger Replay 与原子写入。
    """

    def __init__(
        self,
        auth_service: AuthService | PortfolioSetupWriter,
        portfolio_service: PortfolioService | OpeningStateWriter,
    ) -> None:
        self._auth_service = auth_service
        self._portfolio_service = portfolio_service

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        """使用已确认的 Browser Draft 创建唯一 Portfolio。"""

        return self._auth_service.setup_portfolio(command)

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        """使用已确认的 Browser Draft 初始化 Existing Portfolio。"""

        return self._portfolio_service.initialize_opening_positions(command)


__all__ = ["OpeningImportService"]
