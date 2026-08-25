"""Investment Context 确定性派生事实测试。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from position_pilot.application.investment_context import (
    PriceDirection,
    RecentPriceHistoryFacts,
)
from position_pilot.domain.market_data import HistoricalBars, MarketDataCoverage, OHLCVBar

NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


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
