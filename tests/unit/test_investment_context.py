"""Investment Context 确定性派生事实测试。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.investment_context import (
    HISTORICAL_BUYS_PER_POSITION_LIMIT,
    HistoricalBuyFacts,
    PriceDirection,
    RecentPriceHistoryFacts,
)
from position_pilot.domain.market_data import HistoricalBars, MarketDataCoverage, OHLCVBar
from position_pilot.domain.portfolio import (
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
)

NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def history(first_close: str, latest_close: str) -> HistoricalBars:
    """创建只用于首尾方向与百分比计算的两根 Daily Bars。"""

    first = Decimal(first_close)
    latest = Decimal(latest_close)
    return HistoricalBars(
        ticker="GOOG",
        timeframe="1Day",
        bars=(
            OHLCVBar(
                NOW - timedelta(days=1),
                first,
                first + Decimal("2"),
                first - Decimal("2"),
                first,
                1000,
            ),
            OHLCVBar(
                NOW,
                latest,
                latest + Decimal("2"),
                latest - Decimal("2"),
                latest,
                1200,
            ),
        ),
        source="FAKE_CONTEXT",
        feed="FIXED",
        coverage=MarketDataCoverage.SINGLE_EXCHANGE,
        currency="USD",
        adjustment="ALL",
        fetched_at=NOW,
    )


@pytest.mark.parametrize(
    ("first_close", "latest_close", "change", "percent", "direction"),
    [
        ("200", "210", Decimal("10"), Decimal("5.00"), PriceDirection.UP),
        ("200", "190", Decimal("-10"), Decimal("-5.00"), PriceDirection.DOWN),
        ("200", "200", Decimal("0"), Decimal("0.00"), PriceDirection.FLAT),
    ],
)
def test_recent_price_history_facts_cover_all_directions(
    first_close: str,
    latest_close: str,
    change: Decimal,
    percent: Decimal,
    direction: PriceDirection,
) -> None:
    """UP、DOWN 与 FLAT 均由首尾收盘价稳定计算。"""

    facts = RecentPriceHistoryFacts.from_historical_bars(history(first_close, latest_close))

    assert facts.close_change == change
    assert facts.absolute_close_change == abs(change)
    assert facts.close_change_percent == percent
    assert facts.absolute_close_change_percent == abs(percent)
    assert facts.close_direction is direction


def test_recent_price_history_percent_uses_half_even_two_decimal_rounding() -> None:
    """历史涨跌幅使用与输出契约一致的两位小数银行家舍入。"""

    facts = RecentPriceHistoryFacts.from_historical_bars(history("200", "201.01"))

    assert facts.close_change_percent == Decimal("0.50")


def transaction(
    sequence: int,
    ticker: str,
    action: TransactionAction,
    position_type: PositionType,
) -> Transaction:
    """创建 Historical Buy Projection 使用的固定 Ledger 记录。"""

    return Transaction.create(
        user_id=USER_ID,
        sequence=sequence,
        ticker=ticker,
        action=action,
        price=Decimal(str(100 + sequence)),
        shares=Decimal("1"),
        position_type=position_type,
        occurred_at=NOW + timedelta(minutes=sequence),
    )


def test_historical_buy_facts_are_bounded_by_current_position_type() -> None:
    """历史 BUY 只覆盖当前 Position，并为每类仓位独立截断。"""

    transactions = tuple(
        [
            transaction(sequence, "GOOG", TransactionAction.BUY, PositionType.LONG_TERM)
            for sequence in range(1, 7)
        ]
        + [
            transaction(7, "GOOG", TransactionAction.BUY, PositionType.SWING),
            transaction(8, "GOOG", TransactionAction.SELL, PositionType.LONG_TERM),
            transaction(9, "MSFT", TransactionAction.BUY, PositionType.LONG_TERM),
            transaction(10, "MSFT", TransactionAction.SELL, PositionType.LONG_TERM),
        ]
    )
    state = rebuild_portfolio(
        User.create(
            user_id=USER_ID,
            display_name="Historical Buy Fixture",
            initial_cash=Decimal("2000"),
            created_at=NOW,
        ),
        list(transactions),
        [],
    )

    facts = HistoricalBuyFacts.from_transactions(state, transactions)

    assert HISTORICAL_BUYS_PER_POSITION_LIMIT == 5
    assert facts.total_count == 7
    assert facts.included_count == 6
    assert facts.truncated is True
    assert [record.sequence for record in facts.records] == [2, 3, 4, 5, 6, 7]
    assert [record.position_type for record in facts.records] == [
        PositionType.LONG_TERM,
        PositionType.LONG_TERM,
        PositionType.LONG_TERM,
        PositionType.LONG_TERM,
        PositionType.LONG_TERM,
        PositionType.SWING,
    ]
    assert facts.as_dict()["scope"] == "current_positions_only"
    assert facts.as_dict()["record_type"] == "BUY_ONLY"


def test_historical_buy_facts_reject_mixed_user_ledger() -> None:
    """历史投影边界必须拒绝与 Portfolio Owner 不一致的 Transaction。"""

    state = rebuild_portfolio(
        User.create(
            user_id=USER_ID,
            display_name="Historical Buy Fixture",
            initial_cash=Decimal("2000"),
            created_at=NOW,
        ),
        [transaction(1, "GOOG", TransactionAction.BUY, PositionType.LONG_TERM)],
        [],
    )
    other_user_transaction = Transaction.create(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("100"),
        shares=Decimal("1"),
        position_type=PositionType.LONG_TERM,
        occurred_at=NOW,
    )

    with pytest.raises(ValueError, match="不能混合不同 User"):
        HistoricalBuyFacts.from_transactions(state, (other_user_transaction,))
