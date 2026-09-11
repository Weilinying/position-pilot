"""组合当前持仓与行情的 Portfolio 估值服务。"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from position_pilot.domain.market_data import (
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
    is_current_quote_fresh,
)
from position_pilot.domain.portfolio import PortfolioState
from position_pilot.domain.portfolio_valuation import (
    PortfolioValuation,
    value_portfolio_ticker,
)


class PortfolioReader(Protocol):
    """估值所需的当前 Portfolio 读取边界。"""

    def get_portfolio(self, user_id: UUID) -> PortfolioState: ...


class CurrentQuoteReader(Protocol):
    """估值所需的当前行情读取边界。"""

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]: ...


class PortfolioValuationService:
    """每个 ticker 获取一次行情并计算全部持仓层级。"""

    def __init__(
        self,
        portfolios: PortfolioReader,
        market_data: CurrentQuoteReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._portfolios = portfolios
        self._market_data = market_data
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_current_valuation(self, user_id: UUID) -> PortfolioValuation:
        """返回当前 Portfolio 的逐 ticker 估值。"""

        portfolio = self._portfolios.get_portfolio(user_id)
        tickers = sorted({lot.ticker for lot in portfolio.lots})
        results = []
        for ticker in tickers:
            result = self._market_data.get_current_quote(ticker)
            if (
                result.status is MarketDataStatus.OK
                and result.data is not None
                and not is_current_quote_fresh(result.data, at=self._clock())
            ):
                result = MarketDataResult.failure(
                    MarketDataStatus.STALE,
                    "最新成交时间不可用于当前估值",
                )
            results.append(
                value_portfolio_ticker(
                    portfolio,
                    ticker,
                    status=result.status,
                    quote=result.data,
                    message=result.message,
                )
            )
        return PortfolioValuation(user_id=user_id, tickers=tuple(results))
