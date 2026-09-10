"""Portfolio 当前行情估值测试。"""

from datetime import UTC, datetime
from decimal import Decimal

from position_pilot.application.portfolio_valuation_service import PortfolioValuationService
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.portfolio import (
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
)

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)


def make_portfolio():
    """建立同一 ticker 下两个策略批次。"""

    user = User.create(display_name="Alice", initial_cash=Decimal("1000"), created_at=NOW)
    transactions = [
        Transaction.create(
            user_id=user.id,
            sequence=1,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("100"),
            shares=Decimal("1"),
            position_type=PositionType.SWING,
            occurred_at=NOW,
        ),
        Transaction.create(
            user_id=user.id,
            sequence=2,
            ticker="GOOG",
            action=TransactionAction.BUY,
            price=Decimal("200"),
            shares=Decimal("2"),
            position_type=PositionType.LONG_TERM,
            occurred_at=NOW,
        ),
    ]
    return rebuild_portfolio(user, transactions)


def make_quote() -> MarketQuote:
    """建立一个可用于全部层级的行情快照。"""

    return MarketQuote(
        ticker="GOOG",
        last_price=Decimal("250"),
        bid_price=Decimal("249"),
        ask_price=Decimal("251"),
        last_trade_at=NOW,
        quote_at=NOW,
        source="alpaca",
        feed="iex",
        coverage=MarketDataCoverage.SINGLE_EXCHANGE,
        currency="USD",
        is_delayed=False,
        fetched_at=NOW,
    )


class FakePortfolioReader:
    """返回固定 Portfolio。"""

    def __init__(self, portfolio):
        self.portfolio = portfolio

    def get_portfolio(self, user_id):
        assert user_id == self.portfolio.user_id
        return self.portfolio


class FakeQuoteReader:
    """记录调用并返回固定行情结果。"""

    def __init__(self, result):
        self.result = result
        self.tickers: list[str] = []

    def get_current_quote(self, ticker):
        self.tickers.append(ticker)
        return self.result


def test_values_ticker_types_and_lots_with_one_quote() -> None:
    """同一 ticker 的总体、类型和批次应共享一次报价并各自重算。"""

    portfolio = make_portfolio()
    quotes = FakeQuoteReader(MarketDataResult.success(make_quote()))

    result = PortfolioValuationService(
        FakePortfolioReader(portfolio),
        quotes,
    ).get_current_valuation(portfolio.user_id)

    assert quotes.tickers == ["GOOG"]
    ticker = result.tickers[0]
    assert ticker.metrics is not None
    assert ticker.metrics.shares == Decimal("3.00000000")
    assert ticker.metrics.market_value == Decimal("750.00000000")
    assert ticker.metrics.unrealized_pnl == Decimal("249.30000000")
    assert ticker.metrics.unrealized_pnl_percent == Decimal("49.79")
    assert [item.position_type for item in ticker.position_types] == [
        PositionType.SWING,
        PositionType.LONG_TERM,
    ]
    assert len(ticker.lots) == 2


def test_preserves_market_failure_without_inventing_valuation() -> None:
    """行情失败时应保留状态，且不生成任何数值估值。"""

    portfolio = make_portfolio()
    quotes = FakeQuoteReader(
        MarketDataResult.failure(MarketDataStatus.PROVIDER_UNAVAILABLE, "行情暂不可用")
    )

    ticker = (
        PortfolioValuationService(
            FakePortfolioReader(portfolio),
            quotes,
        )
        .get_current_valuation(portfolio.user_id)
        .tickers[0]
    )

    assert ticker.status is MarketDataStatus.PROVIDER_UNAVAILABLE
    assert ticker.message == "行情暂不可用"
    assert ticker.quote is None
    assert ticker.metrics is not None
    assert ticker.metrics.shares == Decimal("3.00000000")
    assert ticker.metrics.market_value is None
    assert len(ticker.position_types) == 2
    assert len(ticker.lots) == 2
