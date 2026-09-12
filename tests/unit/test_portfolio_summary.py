"""首页核算与行情组合的定向测试。"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from position_pilot.application.portfolio_summary_service import PortfolioSummaryService
from position_pilot.application.portfolio_valuation_service import PortfolioValuationService
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.portfolio import (
    LotAllocation,
    PortfolioState,
    PositionType,
    ReplayResult,
    Transaction,
    TransactionAction,
    User,
    replay_portfolio,
)

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def make_replay(*, closed: bool = False, second_ticker: bool = False) -> ReplayResult:
    """构建已实现 $79、未实现 $60 的账本或全清仓版本。"""

    user = User.create(display_name="Summary", initial_cash=Decimal("5000"), created_at=NOW)
    buy = Transaction.create(
        user_id=user.id,
        sequence=1,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("100"),
        shares=Decimal("10"),
        position_type=PositionType.SWING,
        occurred_at=NOW - timedelta(days=2),
    )
    sell = Transaction.create(
        user_id=user.id,
        sequence=2,
        ticker="GOOG",
        action=TransactionAction.SELL,
        price=Decimal("120"),
        shares=Decimal("10" if closed else "4"),
        fee=Decimal("1"),
        position_type=PositionType.SWING,
        occurred_at=NOW - timedelta(days=1),
    )
    transactions = [buy, sell]
    if second_ticker:
        transactions.append(
            Transaction.create(
                user_id=user.id,
                sequence=3,
                ticker="TSLA",
                action=TransactionAction.BUY,
                price=Decimal("100"),
                shares=Decimal("1"),
                occurred_at=NOW,
            )
        )
    allocation = LotAllocation.create(
        user_id=user.id, sell_transaction_id=sell.id, lot_id=buy.id, shares=sell.shares
    )
    return replay_portfolio(user, transactions, lot_allocations=[allocation])


@dataclass
class FakeReader:
    """记录读取次数，阻止首页重复读取账本。"""

    replay: ReplayResult
    reads: list[UUID] = field(default_factory=list)

    def get_replay(self, user_id: UUID) -> ReplayResult:
        assert user_id == self.replay.portfolio.user_id
        self.reads.append(user_id)
        return self.replay

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        raise AssertionError("首页应复用已有 ReplayResult")


@dataclass
class FakeQuotes:
    """按 ticker 返回确定性行情与明确失败。"""

    calls: list[str] = field(default_factory=list)
    stale: bool = False

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        self.calls.append(ticker)
        if ticker == "TSLA":
            return MarketDataResult.failure(MarketDataStatus.PROVIDER_UNAVAILABLE, "Unavailable")
        return MarketDataResult.success(
            MarketQuote(
                ticker=ticker,
                last_price=Decimal("110"),
                bid_price=Decimal("109"),
                ask_price=Decimal("111"),
                last_trade_at=NOW - timedelta(days=8) if self.stale else NOW,
                quote_at=NOW,
                source="alpaca",
                feed="iex",
                coverage=MarketDataCoverage.SINGLE_EXCHANGE,
                currency="USD",
                is_delayed=False,
                fetched_at=NOW,
            )
        )


def make_summary_service(
    replay: ReplayResult, quotes: FakeQuotes
) -> tuple[PortfolioSummaryService, FakeReader]:
    """装配不依赖真实数据源的首页服务。"""

    reader = FakeReader(replay)
    valuation = PortfolioValuationService(reader, quotes, clock=lambda: NOW)
    return PortfolioSummaryService(reader, valuation), reader


def test_summary_reuses_one_replay_and_one_quote() -> None:
    """摘要与明细使用同一快照，且前端不需要重新计算收益。"""

    replay = make_replay()
    quotes = FakeQuotes()
    service, reader = make_summary_service(replay, quotes)
    result = service.get_summary(replay.portfolio.user_id)
    assert reader.reads == [replay.portfolio.user_id]
    assert quotes.calls == ["GOOG"]
    assert result.portfolio is replay.portfolio
    assert result.totals.realized_pnl == Decimal("79")
    assert result.totals.unrealized_pnl == Decimal("60")
    assert result.totals.total_pnl == Decimal("139")
    assert result.totals.market_value == Decimal("660")
    assert result.totals.valuation_complete
    assert result.tickers[0].position_types[0].metrics == result.totals


def test_partial_quotes_do_not_make_partial_portfolio_total() -> None:
    """一只缺行情，已实现与可用股票仍有值，组合当前收益明确为空。"""

    replay = make_replay(second_ticker=True)
    service, _ = make_summary_service(replay, FakeQuotes())
    result = service.get_summary(replay.portfolio.user_id)
    assert result.totals.realized_pnl == Decimal("79")
    assert result.totals.unrealized_pnl is None
    assert result.totals.total_pnl is None
    assert result.totals.market_value is None
    assert not result.totals.valuation_complete
    assert result.tickers[0].metrics.total_pnl == Decimal("139")
    assert result.tickers[1].metrics.total_pnl is None


def test_stale_quotes_preserve_realized_pnl() -> None:
    """行情新鲜度规则仍作用于首页，历史收益不受影响。"""

    replay = make_replay()
    service, _ = make_summary_service(replay, FakeQuotes(stale=True))
    result = service.get_summary(replay.portfolio.user_id)
    assert result.valuation.tickers[0].status is MarketDataStatus.STALE
    assert result.totals.realized_pnl == Decimal("79")
    assert result.totals.unrealized_pnl is None


def test_closed_and_empty_portfolios_have_zero_unrealized_without_quotes() -> None:
    """已清仓收益仍存在，空持仓无需行情即可得出未实现零。"""

    replay = make_replay(closed=True)
    quotes = FakeQuotes()
    service, _ = make_summary_service(replay, quotes)
    result = service.get_summary(replay.portfolio.user_id)
    assert result.portfolio.lots == ()
    assert result.tickers[0].ticker == "GOOG"
    assert result.totals.realized_pnl == Decimal("199")
    assert result.totals.unrealized_pnl == 0
    assert result.totals.total_pnl == Decimal("199")
    assert quotes.calls == []
    empty = replace(replay, sell_allocation_results=())
    service, _ = make_summary_service(empty, quotes)
    result = service.get_summary(empty.portfolio.user_id)
    assert result.tickers == ()
    assert result.totals.total_pnl == 0


def test_current_classification_does_not_move_past_sale_pnl() -> None:
    """历史波段收益与当前长期未实现收益合并展示，但不重写归属。"""

    replay = make_replay()
    current = replace(
        replay.portfolio,
        lots=tuple(
            replace(lot, position_type=PositionType.LONG_TERM) for lot in replay.portfolio.lots
        ),
    )
    replay = replace(replay, portfolio=current)
    service, _ = make_summary_service(replay, FakeQuotes())
    result = service.get_summary(replay.portfolio.user_id)
    swing, long_term = result.tickers[0].position_types
    assert swing.position_type is PositionType.SWING
    assert swing.metrics.realized_pnl == Decimal("79")
    assert swing.metrics.unrealized_pnl == 0
    assert long_term.metrics.realized_pnl == 0
    assert long_term.metrics.unrealized_pnl == Decimal("60")
