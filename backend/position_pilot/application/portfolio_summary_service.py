"""首页组合读取；复用账本核算与行情估值的独立职责。"""

from typing import Protocol
from uuid import UUID

from position_pilot.application.portfolio_valuation_service import PortfolioValuationService
from position_pilot.domain.portfolio import ReplayResult
from position_pilot.domain.portfolio_accounting import calculate_portfolio_accounting
from position_pilot.domain.portfolio_summary import PortfolioSummary, summarize_portfolio


class ReplayReader(Protocol):
    """首页读取所需的单次完整重放。"""

    def get_replay(self, user_id: UUID) -> ReplayResult: ...


class PortfolioSummaryService:
    """同一份重放结果上计算历史收益与实时估值。"""

    def __init__(self, portfolios: ReplayReader, valuation: PortfolioValuationService) -> None:
        self._portfolios = portfolios
        self._valuation = valuation

    def get_summary(self, user_id: UUID) -> PortfolioSummary:
        """每个当前 ticker 只请求一次行情，全部清仓时不请求行情。"""

        replay = self._portfolios.get_replay(user_id)
        accounting = calculate_portfolio_accounting(replay)
        valuation = self._valuation.value_portfolio(replay.portfolio)
        return summarize_portfolio(replay.portfolio, accounting, valuation)
