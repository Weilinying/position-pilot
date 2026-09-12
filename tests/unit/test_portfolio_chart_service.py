"""Portfolio Chart Service 的日期、事实与行情边界测试。"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.portfolio_chart_service import (
    ChartAssetNotFound,
    ChartRange,
    PortfolioChartService,
    resolve_chart_window,
)
from position_pilot.application.portfolio_service import PortfolioReplaySnapshot
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    OHLCVBar,
)
from position_pilot.domain.portfolio import (
    BuyTransactionCorrection,
    LotAllocation,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    apply_buy_transaction_corrections,
    replay_portfolio,
)

NOW = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)
USER_ID = UUID("00000000-0000-0000-0000-000000000013")


@dataclass(slots=True)
class FakeMarketData:
    """记录查询并返回固定 Historical Result。"""

    result: MarketDataResult[HistoricalBars]
    queries: list[HistoricalBarsQuery] = field(default_factory=list)

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        self.queries.append(query)
        return self.result


@dataclass(slots=True)
class FakePortfolioReader:
    """返回固定的一次 Replay 快照。"""

    snapshot: PortfolioReplaySnapshot

    def get_replay_snapshot(self, user_id: UUID) -> PortfolioReplaySnapshot:
        return self.snapshot


def make_user() -> User:
    return User.create(
        user_id=USER_ID,
        display_name="Chart",
        initial_cash=Decimal("10000"),
        created_at=NOW,
    )


def make_buy(
    user: User,
    *,
    sequence: int,
    ticker: str = "GOOG",
    occurred_at: datetime = datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
    shares: str = "4",
    price: str = "100",
    position_type: PositionType = PositionType.SWING,
) -> Transaction:
    return Transaction.create(
        user_id=user.id,
        sequence=sequence,
        ticker=ticker,
        action=TransactionAction.BUY,
        price=Decimal(price),
        shares=Decimal(shares),
        position_type=position_type,
        occurred_at=occurred_at,
    )


def make_sell(
    user: User,
    *,
    sequence: int,
    occurred_at: datetime = datetime(2026, 9, 11, 15, 0, tzinfo=UTC),
    shares: str = "2",
) -> Transaction:
    return Transaction.create(
        user_id=user.id,
        sequence=sequence,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price=Decimal("120"),
        shares=Decimal(shares),
        fee=Decimal("1"),
        occurred_at=occurred_at,
    )


def make_snapshot(
    transactions: list[Transaction],
    *,
    corrections: list[BuyTransactionCorrection] | None = None,
) -> PortfolioReplaySnapshot:
    user = make_user()
    allocations = []
    if any(transaction.action is TransactionAction.SELL for transaction in transactions):
        buy = next(
            transaction
            for transaction in transactions
            if transaction.action is TransactionAction.BUY
        )
        sell = next(
            transaction
            for transaction in transactions
            if transaction.action is TransactionAction.SELL
        )
        allocations.append(
            LotAllocation.create(
                user_id=user.id,
                sell_transaction_id=sell.id,
                lot_id=buy.id,
                shares=sell.shares,
            )
        )
    replay = replay_portfolio(
        user,
        transactions,
        lot_allocations=allocations,
        buy_transaction_corrections=corrections,
    )
    effective_transactions = tuple(
        apply_buy_transaction_corrections(user, transactions, corrections)
    )
    return PortfolioReplaySnapshot(replay=replay, effective_transactions=effective_transactions)


def make_bars(*timestamps: datetime) -> HistoricalBars:
    return HistoricalBars(
        ticker="GOOG",
        timeframe="1Day",
        bars=tuple(
            OHLCVBar(
                timestamp=timestamp,
                open=Decimal("100"),
                high=Decimal("125"),
                low=Decimal("95"),
                close=Decimal("120"),
                volume=1000,
            )
            for timestamp in timestamps
        ),
        source="ALPACA",
        feed="SIP",
        coverage=MarketDataCoverage.CONSOLIDATED,
        currency="USD",
        adjustment="ALL",
        fetched_at=NOW,
    )


def test_calendar_ranges_clamp_month_end_and_use_current_new_york_date() -> None:
    window = resolve_chart_window(
        ChartRange.ONE_MONTH,
        anchor_date=date(2026, 5, 31),
        now=NOW,
    )
    assert window.requested_start == date(2026, 4, 30)
    assert window.requested_end == date(2026, 5, 31)
    assert window.query_start == datetime(2026, 4, 30, 4, 0, tzinfo=UTC)
    current = resolve_chart_window("3M", anchor_date=None, now=NOW)
    assert current.anchor_date == date(2026, 9, 15)
    assert current.query_end == NOW - timedelta(minutes=15)


@pytest.mark.parametrize(
    ("chart_range", "requested_start"),
    [
        (ChartRange.THREE_MONTHS, date(2026, 6, 15)),
        (ChartRange.SIX_MONTHS, date(2026, 3, 15)),
        (ChartRange.ONE_YEAR, date(2025, 9, 15)),
    ],
)
def test_chart_ranges_use_calendar_months(
    chart_range: ChartRange,
    requested_start: date,
) -> None:
    window = resolve_chart_window(chart_range, anchor_date=None, now=NOW)
    assert window.requested_start == requested_start
    assert window.requested_end == date(2026, 9, 15)


def test_chart_rejects_future_anchor_date() -> None:
    with pytest.raises(ValueError, match="anchor_date"):
        resolve_chart_window(
            ChartRange.THREE_MONTHS,
            anchor_date=date(2026, 9, 16),
            now=NOW,
        )


def test_chart_rejects_unowned_ticker_before_provider_call() -> None:
    user = make_user()
    market_data = FakeMarketData(MarketDataResult.failure(MarketDataStatus.NO_DATA, "unused"))
    snapshot = make_snapshot([make_buy(user, sequence=1)])
    service = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    )
    with pytest.raises(ChartAssetNotFound):
        service.get_chart(user.id, "AAPL", ChartRange.THREE_MONTHS)
    assert market_data.queries == []


def test_chart_filters_incomplete_bars_and_returns_actual_metadata() -> None:
    user = make_user()
    snapshot = make_snapshot([make_buy(user, sequence=1)])
    market_data = FakeMarketData(
        MarketDataResult.success(
            make_bars(
                datetime(2026, 9, 14, 4, 0, tzinfo=UTC),
                datetime(2026, 9, 15, 4, 0, tzinfo=UTC),
            )
        )
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "goog", ChartRange.THREE_MONTHS)
    assert result.status is MarketDataStatus.OK
    assert len(result.bars) == 1
    assert result.bars[0].timestamp == datetime(2026, 9, 14, 4, 0, tzinfo=UTC)
    assert (result.source, result.feed, result.adjustment, result.timeframe) == (
        "ALPACA",
        "SIP",
        "ALL",
        "1Day",
    )
    assert result.current_cost is not None
    assert result.cost_basis_comparable is False


def test_chart_staleness_uses_selected_historical_window_end() -> None:
    user = make_user()
    snapshot = make_snapshot([make_buy(user, sequence=1)])
    market_data = FakeMarketData(
        MarketDataResult.success(make_bars(datetime(2026, 6, 20, 4, 0, tzinfo=UTC)))
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(
        user.id,
        "GOOG",
        ChartRange.ONE_MONTH,
        anchor_date=date(2026, 6, 30),
    )
    assert result.status is MarketDataStatus.STALE
    assert len(result.bars) == 1
    assert market_data.queries[0].end == datetime(2026, 7, 1, 4, 0, tzinfo=UTC)


def test_provider_failure_keeps_cost_and_transaction_facts() -> None:
    user = make_user()
    buy = make_buy(user, sequence=1)
    sell = make_sell(user, sequence=2)
    snapshot = make_snapshot([buy, sell])
    market_data = FakeMarketData(
        MarketDataResult.failure(MarketDataStatus.PROVIDER_UNAVAILABLE, "行情不可用")
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "GOOG", ChartRange.THREE_MONTHS)
    assert result.status is MarketDataStatus.PROVIDER_UNAVAILABLE
    assert result.bars == ()
    assert result.current_cost is not None
    assert len(result.markers) == 2
    assert result.markers[1].transactions[0].allocations[0].realized_pnl == Decimal("39.00000000")


def test_same_day_transactions_are_grouped_and_missing_bar_is_explicit() -> None:
    user = make_user()
    buy_one = make_buy(user, sequence=1, occurred_at=datetime(2026, 9, 9, 14, 0, tzinfo=UTC))
    buy_two = make_buy(user, sequence=2, occurred_at=datetime(2026, 9, 9, 15, 0, tzinfo=UTC))
    snapshot = make_snapshot([buy_one, buy_two])
    market_data = FakeMarketData(
        MarketDataResult.success(make_bars(datetime(2026, 9, 8, 4, 0, tzinfo=UTC)))
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "GOOG", ChartRange.THREE_MONTHS)
    assert len(result.markers) == 1
    assert result.markers[0].market_date == date(2026, 9, 9)
    assert result.markers[0].has_bar is False
    assert [item.transaction_id for item in result.markers[0].transactions] == [
        buy_one.id,
        buy_two.id,
    ]


def test_closed_ticker_remains_accessible_from_transaction_history() -> None:
    user = make_user()
    buy = make_buy(user, sequence=1)
    sell = make_sell(user, sequence=2, shares="4")
    snapshot = make_snapshot([buy, sell])
    market_data = FakeMarketData(
        MarketDataResult.success(make_bars(datetime(2026, 9, 10, 4, 0, tzinfo=UTC)))
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "GOOG", ChartRange.THREE_MONTHS)
    assert result.current_cost is None
    assert result.cost_line_unavailable_reason == "NO_CURRENT_POSITION"
    assert len(result.markers) == 2


def test_buy_correction_changes_effective_marker_and_sell_allocation() -> None:
    user = make_user()
    buy = make_buy(user, sequence=1)
    sell = make_sell(user, sequence=2)
    correction = BuyTransactionCorrection.create(
        user_id=user.id,
        transaction_id=buy.id,
        price=Decimal("105"),
        shares=Decimal("4"),
        occurred_at=buy.occurred_at,
        reason="修正",
        corrected_at=NOW,
    )
    snapshot = make_snapshot([buy, sell], corrections=[correction])
    market_data = FakeMarketData(
        MarketDataResult.success(make_bars(datetime(2026, 9, 10, 4, 0, tzinfo=UTC)))
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "GOOG", ChartRange.THREE_MONTHS)
    assert result.markers[0].transactions[0].price == Decimal("105.00000000")
    assert result.markers[1].transactions[0].allocations[0].released_cost == Decimal("210.00000000")
    assert result.markers[1].transactions[0].allocations[0].realized_pnl == Decimal("29.00000000")


def test_sell_marker_preserves_allocations_across_position_types() -> None:
    user = make_user()
    swing_buy = make_buy(user, sequence=1, shares="2", position_type=PositionType.SWING)
    long_term_buy = make_buy(
        user,
        sequence=2,
        shares="3",
        position_type=PositionType.LONG_TERM,
        occurred_at=datetime(2026, 9, 10, 16, 0, tzinfo=UTC),
    )
    sell = make_sell(user, sequence=3, shares="3")
    allocations = [
        LotAllocation.create(
            user_id=user.id,
            sell_transaction_id=sell.id,
            lot_id=swing_buy.id,
            shares=Decimal("2"),
        ),
        LotAllocation.create(
            user_id=user.id,
            sell_transaction_id=sell.id,
            lot_id=long_term_buy.id,
            shares=Decimal("1"),
        ),
    ]
    replay = replay_portfolio(
        user,
        [swing_buy, long_term_buy, sell],
        lot_allocations=allocations,
    )
    snapshot = PortfolioReplaySnapshot(
        replay=replay,
        effective_transactions=tuple([swing_buy, long_term_buy, sell]),
    )
    market_data = FakeMarketData(
        MarketDataResult.success(make_bars(datetime(2026, 9, 11, 4, 0, tzinfo=UTC)))
    )
    result = PortfolioChartService(
        FakePortfolioReader(snapshot),
        market_data,
        clock=lambda: NOW,
    ).get_chart(user.id, "GOOG", ChartRange.THREE_MONTHS)
    sell_marker = next(
        marker
        for marker in result.markers
        if marker.transactions[0].action is TransactionAction.SELL
    )
    assert {
        allocation.position_type_at_sale for allocation in sell_marker.transactions[0].allocations
    } == {PositionType.SWING, PositionType.LONG_TERM}
