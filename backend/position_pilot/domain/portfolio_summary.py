"""首页按同一持仓快照汇总已实现收益与当前估值。"""

from dataclasses import dataclass
from decimal import Decimal

from position_pilot.domain.portfolio import DECIMAL_QUANTUM, PortfolioState, PositionType
from position_pilot.domain.portfolio_accounting import PortfolioAccounting
from position_pilot.domain.portfolio_valuation import PortfolioValuation, ValuationMetrics


@dataclass(frozen=True, slots=True)
class SummaryMetrics:
    """完整行情缺失时保留已实现收益，当前金额明确为空。"""

    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    total_pnl: Decimal | None
    market_value: Decimal | None
    valuation_complete: bool


@dataclass(frozen=True, slots=True)
class PositionTypeSummary:
    """历史卖出类型与当前持仓类型各自汇总后合并展示。"""

    position_type: PositionType
    metrics: SummaryMetrics


@dataclass(frozen=True, slots=True)
class TickerSummary:
    """包括已清仓 ticker 的收益摘要。"""

    ticker: str
    metrics: SummaryMetrics
    position_types: tuple[PositionTypeSummary, ...]


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    """首页组合视图；核算与估值仍保留各自结构。"""

    portfolio: PortfolioState
    accounting: PortfolioAccounting
    valuation: PortfolioValuation
    totals: SummaryMetrics
    tickers: tuple[TickerSummary, ...]


def _metrics(realized: Decimal, valuations: tuple[ValuationMetrics, ...]) -> SummaryMetrics:
    complete = all(
        item.unrealized_pnl is not None and item.market_value is not None for item in valuations
    )
    unrealized = (
        sum(
            (item.unrealized_pnl for item in valuations if item.unrealized_pnl is not None),
            Decimal("0"),
        ).quantize(DECIMAL_QUANTUM)
        if complete
        else None
    )
    market_value = (
        sum(
            (item.market_value for item in valuations if item.market_value is not None),
            Decimal("0"),
        ).quantize(DECIMAL_QUANTUM)
        if complete
        else None
    )
    return SummaryMetrics(
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        total_pnl=realized + unrealized if unrealized is not None else None,
        market_value=market_value,
        valuation_complete=complete,
    )


def summarize_portfolio(
    portfolio: PortfolioState,
    accounting: PortfolioAccounting,
    valuation: PortfolioValuation,
) -> PortfolioSummary:
    """按类型到 ticker 聚合；已清仓类型的当前市值与未实现为零。"""

    realized_by_ticker = {item.ticker: item for item in accounting.tickers}
    valued_by_ticker = {item.ticker: item for item in valuation.tickers}
    tickers = []
    for ticker in sorted(realized_by_ticker.keys() | valued_by_ticker.keys()):
        realized = realized_by_ticker.get(ticker)
        valued = valued_by_ticker.get(ticker)
        realized_types = (
            {item.position_type: item.metrics for item in realized.position_types}
            if realized
            else {}
        )
        valued_types = (
            {item.position_type: item.metrics for item in valued.position_types} if valued else {}
        )
        types = tuple(
            PositionTypeSummary(
                position_type=kind,
                metrics=_metrics(
                    realized_types[kind].realized_pnl if kind in realized_types else Decimal("0"),
                    (valued_types[kind],) if kind in valued_types else (),
                ),
            )
            for kind in (PositionType.UNSPECIFIED, PositionType.SWING, PositionType.LONG_TERM)
            if kind in realized_types or kind in valued_types
        )
        tickers.append(
            TickerSummary(
                ticker=ticker,
                metrics=_metrics(
                    realized.metrics.realized_pnl if realized else Decimal("0"),
                    tuple(valued_types.values()),
                ),
                position_types=types,
            )
        )
    return PortfolioSummary(
        portfolio=portfolio,
        accounting=accounting,
        valuation=valuation,
        totals=_metrics(
            accounting.metrics.realized_pnl,
            tuple(
                metrics
                for item in valuation.tickers
                for metrics in (group.metrics for group in item.position_types)
            ),
        ),
        tickers=tuple(tickers),
    )
