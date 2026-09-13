"""Portfolio 已实现收益的确定性聚合。"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

from position_pilot.domain.portfolio import (
    DECIMAL_QUANTUM,
    PositionType,
    ReplayResult,
    SellAllocationResult,
)


@dataclass(frozen=True, slots=True)
class RealizedMetrics:
    """一组卖出分配对应的金额与已实现收益。"""

    gross_proceeds: Decimal
    fee: Decimal
    net_proceeds: Decimal
    released_cost: Decimal
    realized_pnl: Decimal
    realized_pnl_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class SellTransactionResult:
    """一笔 SELL 的已实现收益及其批次分配明细。"""

    transaction_id: UUID
    ticker: str
    occurred_at: datetime
    metrics: RealizedMetrics
    allocations: tuple[SellAllocationResult, ...]


@dataclass(frozen=True, slots=True)
class PositionTypeAccounting:
    """一个仓位类型在已记录卖出中的收益汇总。"""

    position_type: PositionType
    metrics: RealizedMetrics


@dataclass(frozen=True, slots=True)
class TickerAccounting:
    """一个 Ticker 在已记录卖出中的收益与类型分项。"""

    ticker: str
    metrics: RealizedMetrics
    position_types: tuple[PositionTypeAccounting, ...]


@dataclass(frozen=True, slots=True)
class PortfolioAccounting:
    """Portfolio 级已实现收益、卖出明细与 Ticker 汇总。"""

    user_id: UUID
    metrics: RealizedMetrics
    transactions: tuple[SellTransactionResult, ...]
    tickers: tuple[TickerAccounting, ...]


_POSITION_TYPE_ORDER = (
    PositionType.UNSPECIFIED,
    PositionType.SWING,
    PositionType.LONG_TERM,
)


def _quantize(value: Decimal) -> Decimal:
    """按 Portfolio 统一精度量化派生金额。"""

    return value.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)


def _metrics(results: list[SellAllocationResult]) -> RealizedMetrics:
    """从 SELL 分配结果聚合金额并计算整体收益率。"""

    gross_proceeds = _quantize(
        sum((result.allocated_gross_proceeds for result in results), Decimal("0"))
    )
    fee = _quantize(sum((result.allocated_fee for result in results), Decimal("0")))
    net_proceeds = _quantize(
        sum((result.allocated_net_proceeds for result in results), Decimal("0"))
    )
    released_cost = _quantize(sum((result.released_cost for result in results), Decimal("0")))
    realized_pnl = _quantize(sum((result.realized_pnl for result in results), Decimal("0")))
    realized_pnl_percent = (
        None if released_cost == 0 else _quantize(realized_pnl / released_cost * Decimal("100"))
    )
    return RealizedMetrics(
        gross_proceeds=gross_proceeds,
        fee=fee,
        net_proceeds=net_proceeds,
        released_cost=released_cost,
        realized_pnl=realized_pnl,
        realized_pnl_percent=realized_pnl_percent,
    )


def calculate_portfolio_accounting(replay: ReplayResult) -> PortfolioAccounting:
    """从同一次 Replay 的 SELL 分配结果生成 Portfolio 已实现收益汇总。"""

    allocation_results = list(replay.sell_allocation_results)
    allocations_by_transaction: dict[UUID, list[SellAllocationResult]] = {}
    allocations_by_ticker: dict[str, list[SellAllocationResult]] = {}
    for result in allocation_results:
        allocations_by_transaction.setdefault(result.transaction_id, []).append(result)
        allocations_by_ticker.setdefault(result.ticker, []).append(result)

    transaction_results = tuple(
        SellTransactionResult(
            transaction_id=transaction_id,
            ticker=rows[0].ticker,
            occurred_at=rows[0].occurred_at,
            metrics=_metrics(rows),
            allocations=tuple(sorted(rows, key=lambda row: row.lot_id.hex)),
        )
        for transaction_id, rows in sorted(
            allocations_by_transaction.items(),
            key=lambda item: (item[1][0].occurred_at, item[0].hex),
            reverse=True,
        )
    )

    ticker_results = tuple(
        TickerAccounting(
            ticker=ticker,
            metrics=_metrics(rows),
            position_types=tuple(
                PositionTypeAccounting(
                    position_type=position_type,
                    metrics=_metrics(
                        [row for row in rows if row.position_type_at_sale is position_type]
                    ),
                )
                for position_type in _POSITION_TYPE_ORDER
                if any(row.position_type_at_sale is position_type for row in rows)
            ),
        )
        for ticker, rows in sorted(allocations_by_ticker.items())
    )

    return PortfolioAccounting(
        user_id=replay.portfolio.user_id,
        metrics=_metrics(allocation_results),
        transactions=transaction_results,
        tickers=ticker_results,
    )
