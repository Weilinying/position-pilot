"""Portfolio 入口下的历史日线图表数据服务。"""

import calendar
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from position_pilot.application.market_context_service import (
    is_completed_daily_bar,
    is_historical_bars_stale,
)
from position_pilot.application.market_data_service import (
    HistoricalBarsQuery,
)
from position_pilot.application.portfolio_service import PortfolioReplaySnapshot
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    OHLCVBar,
)
from position_pilot.domain.portfolio import (
    PositionType,
    SellAllocationResult,
    TransactionAction,
    normalize_ticker,
)

_NEW_YORK = ZoneInfo("America/New_York")
_HISTORICAL_DELAY = timedelta(minutes=15)
_HISTORICAL_LIMIT = 1000
_RANGE_MONTHS = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12}


class ChartRange(StrEnum):
    """图表支持的日历时间范围。"""

    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    ONE_YEAR = "1Y"


class ChartAssetNotFound(LookupError):
    """Ticker 不属于当前用户可访问的 Portfolio / Transaction 事实。"""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"没有找到可查看的 Portfolio Asset: {ticker}")


@dataclass(frozen=True, slots=True)
class ChartWindow:
    """由日历范围解析出的请求日期与 Provider 时间窗口。"""

    chart_range: ChartRange
    anchor_date: date
    requested_start: date
    requested_end: date
    query_start: datetime
    query_end: datetime


@dataclass(frozen=True, slots=True)
class ChartCurrentCost:
    """当前仍有持仓时的成本摘要。"""

    shares: Decimal
    average_cost: Decimal
    cost_basis: Decimal


@dataclass(frozen=True, slots=True)
class ChartSellAllocation:
    """图表卖出标记中保留的批次分配审计字段。"""

    lot_id: UUID
    source: str
    shares: Decimal
    position_type_at_sale: PositionType
    allocated_gross_proceeds: Decimal
    allocated_fee: Decimal
    allocated_net_proceeds: Decimal
    released_cost: Decimal
    realized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class ChartTransaction:
    """按纽约市场日期展示的一笔有效 BUY / SELL。"""

    transaction_id: UUID
    action: TransactionAction
    occurred_at: datetime
    market_date: date
    shares: Decimal
    price: Decimal
    fee: Decimal
    fee_schedule: str
    position_type: PositionType
    allocations: tuple[ChartSellAllocation, ...]


@dataclass(frozen=True, slots=True)
class ChartTransactionMarker:
    """同一纽约市场日期下的交易集合。"""

    market_date: date
    has_bar: bool
    transactions: tuple[ChartTransaction, ...]


@dataclass(frozen=True, slots=True)
class PortfolioChart:
    """Portfolio Chart API 的结构化结果。"""

    user_id: UUID
    ticker: str
    chart_range: ChartRange
    anchor_date: date
    requested_start: date
    requested_end: date
    timeframe: str
    status: MarketDataStatus
    message: str | None
    bars: tuple[OHLCVBar, ...]
    source: str | None
    feed: str | None
    coverage: MarketDataCoverage | None
    currency: str | None
    adjustment: str | None
    fetched_at: datetime | None
    current_cost: ChartCurrentCost | None
    cost_basis_comparable: bool
    cost_line_unavailable_reason: str
    markers: tuple[ChartTransactionMarker, ...]


class PortfolioChartReader(Protocol):
    """Chart Service 所需的一次 Portfolio Replay 快照读取边界。"""

    def get_replay_snapshot(self, user_id: UUID) -> PortfolioReplaySnapshot: ...


class HistoricalBarsReader(Protocol):
    """Chart Service 所需的 provider-neutral 日线读取边界。"""

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]: ...


def _subtract_calendar_months(value: date, months: int) -> date:
    """按日历月份回退，并把月末日期夹到目标月份最后一天。"""

    month_index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _new_york_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=_NEW_YORK)


def resolve_chart_window(
    chart_range: ChartRange | str,
    *,
    anchor_date: date | None,
    now: datetime,
) -> ChartWindow:
    """把日历范围解析成明确日期和带时区的 Provider 查询窗口。"""

    try:
        normalized_range = ChartRange(chart_range)
    except ValueError as error:
        raise ValueError("range 必须是 1M、3M、6M 或 1Y") from error
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Chart clock 必须包含时区")
    now_utc = now.astimezone(UTC)
    current_new_york_date = now_utc.astimezone(_NEW_YORK).date()
    resolved_anchor = anchor_date or current_new_york_date
    if resolved_anchor > current_new_york_date:
        raise ValueError("anchor_date 不能晚于当前纽约市场日期")
    requested_start = _subtract_calendar_months(
        resolved_anchor,
        _RANGE_MONTHS[normalized_range.value],
    )
    next_day_midnight = _new_york_midnight(resolved_anchor + timedelta(days=1)).astimezone(UTC)
    query_end = (
        min(next_day_midnight, now_utc - _HISTORICAL_DELAY)
        if resolved_anchor == current_new_york_date
        else next_day_midnight
    )
    query_start = _new_york_midnight(requested_start).astimezone(UTC)
    return ChartWindow(
        chart_range=normalized_range,
        anchor_date=resolved_anchor,
        requested_start=requested_start,
        requested_end=resolved_anchor,
        query_start=query_start,
        query_end=query_end,
    )


def _bar_market_date(bar: OHLCVBar) -> date:
    return bar.timestamp.astimezone(_NEW_YORK).date()


def _current_cost(snapshot: PortfolioReplaySnapshot, ticker: str) -> ChartCurrentCost | None:
    positions = [
        position for position in snapshot.replay.portfolio.positions if position.ticker == ticker
    ]
    if not positions:
        return None
    shares = sum((position.shares for position in positions), Decimal("0"))
    cost_basis = sum((position.cost_basis for position in positions), Decimal("0"))
    return ChartCurrentCost(
        shares=shares,
        average_cost=(cost_basis / shares).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_HALF_EVEN,
        ),
        cost_basis=cost_basis,
    )


def _allocation_by_transaction(
    allocations: tuple[SellAllocationResult, ...],
) -> dict[UUID, tuple[ChartSellAllocation, ...]]:
    grouped: dict[UUID, list[ChartSellAllocation]] = {}
    for allocation in allocations:
        grouped.setdefault(allocation.transaction_id, []).append(
            ChartSellAllocation(
                lot_id=allocation.lot_id,
                source=allocation.source.value,
                shares=allocation.shares,
                position_type_at_sale=allocation.position_type_at_sale,
                allocated_gross_proceeds=allocation.allocated_gross_proceeds,
                allocated_fee=allocation.allocated_fee,
                allocated_net_proceeds=allocation.allocated_net_proceeds,
                released_cost=allocation.released_cost,
                realized_pnl=allocation.realized_pnl,
            )
        )
    return {
        transaction_id: tuple(sorted(rows, key=lambda row: row.lot_id.hex))
        for transaction_id, rows in grouped.items()
    }


def _markers(
    snapshot: PortfolioReplaySnapshot,
    *,
    ticker: str,
    window: ChartWindow,
    bar_dates: set[date],
) -> tuple[ChartTransactionMarker, ...]:
    allocations_by_transaction = _allocation_by_transaction(snapshot.replay.sell_allocation_results)
    transactions = (
        transaction
        for transaction in snapshot.effective_transactions
        if transaction.ticker == ticker
        and window.requested_start
        <= transaction.occurred_at.astimezone(_NEW_YORK).date()
        <= window.requested_end
    )
    grouped: dict[date, list[ChartTransaction]] = {}
    for transaction in sorted(
        transactions,
        key=lambda item: (item.occurred_at, item.sequence, item.id.hex),
    ):
        market_date = transaction.occurred_at.astimezone(_NEW_YORK).date()
        grouped.setdefault(market_date, []).append(
            ChartTransaction(
                transaction_id=transaction.id,
                action=transaction.action,
                occurred_at=transaction.occurred_at,
                market_date=market_date,
                shares=transaction.shares,
                price=transaction.price,
                fee=transaction.commission,
                fee_schedule=transaction.fee_schedule,
                position_type=transaction.position_type,
                allocations=(
                    allocations_by_transaction.get(transaction.id, ())
                    if transaction.action is TransactionAction.SELL
                    else ()
                ),
            )
        )
    return tuple(
        ChartTransactionMarker(
            market_date=market_date,
            has_bar=market_date in bar_dates,
            transactions=tuple(transactions),
        )
        for market_date, transactions in sorted(grouped.items())
    )


class PortfolioChartService:
    """读取用户可访问资产的日 K，并附上同一 Replay 的交易事实。"""

    def __init__(
        self,
        portfolios: PortfolioChartReader,
        market_data: HistoricalBarsReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._portfolios = portfolios
        self._market_data = market_data
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_chart(
        self,
        user_id: UUID,
        ticker: str,
        chart_range: ChartRange | str,
        *,
        anchor_date: date | None = None,
    ) -> PortfolioChart:
        """返回固定 ticker 的图表数据；未授权资产在行情调用前拒绝。"""

        snapshot = self._portfolios.get_replay_snapshot(user_id)
        try:
            normalized_ticker = normalize_ticker(ticker)
        except (InvalidPortfolioValue, AttributeError):
            raise ChartAssetNotFound(ticker) from None
        available_tickers = {lot.ticker for lot in snapshot.replay.portfolio.lots} | {
            transaction.ticker for transaction in snapshot.effective_transactions
        }
        if normalized_ticker not in available_tickers:
            raise ChartAssetNotFound(normalized_ticker)

        window = resolve_chart_window(chart_range, anchor_date=anchor_date, now=self._clock())

        cost = _current_cost(snapshot, normalized_ticker)
        market_result = self._market_data.get_historical_bars(
            HistoricalBarsQuery(
                ticker=normalized_ticker,
                start=window.query_start,
                end=window.query_end,
                limit=_HISTORICAL_LIMIT,
            )
        )
        if market_result.status is not MarketDataStatus.OK:
            return PortfolioChart(
                user_id=user_id,
                ticker=normalized_ticker,
                chart_range=window.chart_range,
                anchor_date=window.anchor_date,
                requested_start=window.requested_start,
                requested_end=window.requested_end,
                timeframe="1Day",
                status=market_result.status,
                message=market_result.message,
                bars=(),
                source=None,
                feed=None,
                coverage=None,
                currency=None,
                adjustment=None,
                fetched_at=None,
                current_cost=cost,
                cost_basis_comparable=False,
                cost_line_unavailable_reason=(
                    "UNVERIFIED_PRICE_BASIS" if cost is not None else "NO_CURRENT_POSITION"
                ),
                markers=_markers(
                    snapshot,
                    ticker=normalized_ticker,
                    window=window,
                    bar_dates=set(),
                ),
            )

        historical = market_result.data
        assert historical is not None
        if historical.ticker != normalized_ticker or historical.timeframe != "1Day":
            return PortfolioChart(
                user_id=user_id,
                ticker=normalized_ticker,
                chart_range=window.chart_range,
                anchor_date=window.anchor_date,
                requested_start=window.requested_start,
                requested_end=window.requested_end,
                timeframe="1Day",
                status=MarketDataStatus.INVALID_PROVIDER_RESPONSE,
                message="Historical Provider 返回的 ticker 或 timeframe 不符合 Chart Contract",
                bars=(),
                source=None,
                feed=None,
                coverage=None,
                currency=None,
                adjustment=None,
                fetched_at=None,
                current_cost=cost,
                cost_basis_comparable=False,
                cost_line_unavailable_reason=(
                    "UNVERIFIED_PRICE_BASIS" if cost is not None else "NO_CURRENT_POSITION"
                ),
                markers=_markers(
                    snapshot,
                    ticker=normalized_ticker,
                    window=window,
                    bar_dates=set(),
                ),
            )

        completed_bars = tuple(
            bar
            for bar in historical.bars
            if window.requested_start <= _bar_market_date(bar) <= window.requested_end
            and is_completed_daily_bar(bar.timestamp, query_end=window.query_end)
        )
        bar_dates = {_bar_market_date(bar) for bar in completed_bars}
        status = MarketDataStatus.OK
        message: str | None = None
        if not completed_bars:
            status = MarketDataStatus.NO_DATA
            message = "指定范围没有 completed Historical OHLCV"
        elif is_historical_bars_stale(completed_bars[-1].timestamp, query_end=window.query_end):
            status = MarketDataStatus.STALE
            message = "最新 completed Historical Daily Bar 已超过 7 个日历日"
        return PortfolioChart(
            user_id=user_id,
            ticker=normalized_ticker,
            chart_range=window.chart_range,
            anchor_date=window.anchor_date,
            requested_start=window.requested_start,
            requested_end=window.requested_end,
            timeframe=historical.timeframe,
            status=status,
            message=message,
            bars=completed_bars,
            source=historical.source,
            feed=historical.feed,
            coverage=historical.coverage,
            currency=historical.currency,
            adjustment=historical.adjustment,
            fetched_at=historical.fetched_at,
            current_cost=cost,
            cost_basis_comparable=False,
            cost_line_unavailable_reason=(
                "UNVERIFIED_PRICE_BASIS" if cost is not None else "NO_CURRENT_POSITION"
            ),
            markers=_markers(
                snapshot,
                ticker=normalized_ticker,
                window=window,
                bar_dates=bar_dates,
            ),
        )
