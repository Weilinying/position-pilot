"""当前 Portfolio 的确定性行情估值。"""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

from position_pilot.domain.market_data import MarketDataStatus, MarketQuote
from position_pilot.domain.portfolio import DECIMAL_QUANTUM, PortfolioState, PositionType

PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ValuationMetrics:
    """一个持仓层级在同一行情价格下的确定性估值。"""

    shares: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class LotValuation:
    """单个当前剩余批次的估值。"""

    lot_id: UUID
    position_type: PositionType
    metrics: ValuationMetrics


@dataclass(frozen=True, slots=True)
class PositionTypeValuation:
    """单一 ticker 下一种持仓类型的小计。"""

    position_type: PositionType
    metrics: ValuationMetrics


@dataclass(frozen=True, slots=True)
class TickerValuation:
    """单一 ticker 的总体、类型与批次估值。"""

    ticker: str
    status: MarketDataStatus
    quote: MarketQuote | None
    message: str | None
    metrics: ValuationMetrics | None
    position_types: tuple[PositionTypeValuation, ...]
    lots: tuple[LotValuation, ...]


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """Portfolio 当前全部 ticker 的估值结果。"""

    user_id: UUID
    tickers: tuple[TickerValuation, ...]


def calculate_valuation_metrics(
    *,
    shares: Decimal,
    cost_basis: Decimal,
    current_price: Decimal | None,
) -> ValuationMetrics:
    """使用同一价格计算数量、成本、市值与未实现盈亏。"""

    if current_price is None:
        return ValuationMetrics(
            shares=shares,
            average_cost=(cost_basis / shares).quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            cost_basis=cost_basis,
            market_value=None,
            unrealized_pnl=None,
            unrealized_pnl_percent=None,
        )
    market_value = (shares * current_price).quantize(
        DECIMAL_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )
    unrealized_pnl = (market_value - cost_basis).quantize(
        DECIMAL_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )
    return ValuationMetrics(
        shares=shares,
        average_cost=(cost_basis / shares).quantize(
            DECIMAL_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        ),
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=(unrealized_pnl / cost_basis * Decimal("100")).quantize(
            PERCENT_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        ),
    )


def value_portfolio_ticker(
    portfolio: PortfolioState,
    ticker: str,
    *,
    status: MarketDataStatus,
    quote: MarketQuote | None,
    message: str | None,
) -> TickerValuation:
    """在行情可用时一次计算 ticker 各层；失败时保留明确状态。"""

    ticker_lots = tuple(lot for lot in portfolio.lots if lot.ticker == ticker)
    lot_valuations = tuple(
        LotValuation(
            lot_id=lot.id,
            position_type=lot.position_type,
            metrics=calculate_valuation_metrics(
                shares=lot.remaining_shares,
                cost_basis=lot.cost_basis,
                current_price=quote.last_price if quote is not None else None,
            ),
        )
        for lot in ticker_lots
    )
    type_valuations = tuple(
        PositionTypeValuation(
            position_type=position_type,
            metrics=calculate_valuation_metrics(
                shares=sum(
                    (
                        lot.remaining_shares
                        for lot in ticker_lots
                        if lot.position_type is position_type
                    ),
                    Decimal("0"),
                ),
                cost_basis=sum(
                    (lot.cost_basis for lot in ticker_lots if lot.position_type is position_type),
                    Decimal("0"),
                ),
                current_price=quote.last_price if quote is not None else None,
            ),
        )
        for position_type in (
            PositionType.UNSPECIFIED,
            PositionType.SWING,
            PositionType.LONG_TERM,
        )
        if any(lot.position_type is position_type for lot in ticker_lots)
    )
    return TickerValuation(
        ticker=ticker,
        status=status,
        quote=quote,
        message=message,
        metrics=calculate_valuation_metrics(
            shares=sum((lot.remaining_shares for lot in ticker_lots), Decimal("0")),
            cost_basis=sum((lot.cost_basis for lot in ticker_lots), Decimal("0")),
            current_price=quote.last_price if quote is not None else None,
        ),
        position_types=type_valuations,
        lots=lot_valuations,
    )
