"""使用真实 Aliyun LLM 与固定 Context 的 M5 Behavioral Evaluation。"""

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.investment_answer import (
    InvalidStructuredAnswer,
    SourceReference,
    SourceReferenceType,
    UnresolvedSourceReference,
    parse_structured_answer,
    validate_source_references,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
    LLMToolDefinition,
)
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.news_service import NewsQuery
from position_pilot.domain.market_context import MarketRegimeContext, calculate_market_regime
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
    OHLCVBar,
)
from position_pilot.domain.news import NewsArticle, NewsResult, NewsStatus, RecentNews
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)
from position_pilot.integrations.aliyun_llm import AliyunLLMProvider

USER_ID = UUID("00000000-0000-0000-0000-000000000101")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BehavioralCase:
    """固定输入、预期 Tool Trace 与 Human Review 关注点。"""

    id: str
    question: str
    available_cash: Decimal
    positions: tuple[Position, ...]
    market_results: dict[str, MarketDataResult[MarketQuote]]
    expected_tickers: tuple[str, ...]
    expected_status: InvestmentResponseStatus
    human_checks: tuple[str, ...]
    historical_results: dict[str, MarketDataResult[HistoricalBars]] = field(default_factory=dict)
    expected_history_tickers: tuple[str, ...] = ()
    news_results: dict[str, NewsResult[RecentNews]] = field(default_factory=dict)
    expected_news_tickers: tuple[str, ...] = ()
    market_context_result: MarketDataResult[MarketRegimeContext] = field(
        default_factory=lambda: MarketDataResult.failure(
            MarketDataStatus.NO_DATA,
            "固定场景没有 Market Context",
        )
    )
    expected_market_context_calls: int = 0


class FixedPortfolioReader:
    """为真实模型提供固定、完整且可重复的 Portfolio Snapshot。"""

    def __init__(self, case: BehavioralCase) -> None:
        self._state = PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(USER_ID, Decimal("1000"), case.available_cash),
            positions=case.positions,
            transaction_count=0,
        )

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        assert user_id == USER_ID
        return self._state


class FixedMarketData:
    """隔离实时波动，让 Behavioral Eval 只观察真实 LLM 行为。"""

    def __init__(
        self,
        results: dict[str, MarketDataResult[MarketQuote]],
        historical_results: dict[str, MarketDataResult[HistoricalBars]],
    ) -> None:
        self._results = results
        self._historical_results = historical_results
        self.requested_tickers: list[str] = []
        self.quote_results: list[tuple[str, MarketDataResult[MarketQuote]]] = []
        self.historical_queries: list[HistoricalBarsQuery] = []
        self.historical_query_results: list[
            tuple[HistoricalBarsQuery, MarketDataResult[HistoricalBars]]
        ] = []

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        normalized = ticker.strip().upper()
        self.requested_tickers.append(normalized)
        result = self._results.get(
            normalized,
            MarketDataResult.failure(MarketDataStatus.NO_DATA, "固定场景没有该行情"),
        )
        self.quote_results.append((normalized, result))
        return result

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        self.historical_queries.append(query)
        result = self._historical_results.get(
            query.ticker.strip().upper(),
            MarketDataResult.failure(MarketDataStatus.NO_DATA, "固定场景没有该历史行情"),
        )
        self.historical_query_results.append((query, result))
        return result


class FixedNews:
    """为 Behavioral Eval 返回固定 attributed reporting。"""

    def __init__(self, results: dict[str, NewsResult[RecentNews]]) -> None:
        self._results = results
        self.queries: list[NewsQuery] = []
        self.query_results: list[tuple[NewsQuery, NewsResult[RecentNews]]] = []

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        self.queries.append(query)
        result = self._results.get(
            query.ticker.strip().upper(),
            NewsResult.failure(NewsStatus.NO_NEWS_FOUND, "固定窗口没有返回报道"),
        )
        self.query_results.append((query, result))
        return result


class FixedMarketContext:
    """返回固定确定性 Market Regime，并记录实际 Tool 调用。"""

    def __init__(self, result: MarketDataResult[MarketRegimeContext]) -> None:
        self._result = result
        self.request_count = 0
        self.results: list[MarketDataResult[MarketRegimeContext]] = []

    def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]:
        self.request_count += 1
        self.results.append(self._result)
        return self._result


@dataclass(slots=True)
class CountingLLM:
    """记录 Behavioral Case 的 Completion 数，观察是否触发一次 Repair。"""

    delegate: LLMProvider
    completion_count: int = 0
    results: list[LLMResult] = field(default_factory=list)

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
    ) -> LLMResult:
        self.completion_count += 1
        result = self.delegate.complete(messages, tools=tools)
        self.results.append(result)
        return result


class NoopLLM:
    """Diagnostics 回归不应实际调用 Delegate。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
    ) -> LLMResult:
        raise AssertionError("测试不应调用 NoopLLM")


@dataclass(frozen=True, slots=True)
class BehavioralTrace:
    """区分实际 Tool Calls、Final Source 声明与 Response Repair。"""

    tool_tickers: tuple[str, ...]
    history_tickers: tuple[str, ...]
    news_tickers: tuple[str, ...]
    retrieved_quote_sources: tuple[str, ...]
    retrieved_history_sources: tuple[str, ...]
    retrieved_news_sources: tuple[str, ...]
    declared_quote_sources: tuple[str, ...]
    declared_history_sources: tuple[str, ...]
    declared_news_sources: tuple[str, ...]
    market_context_calls: int
    retrieved_market_context_sources: tuple[str, ...]
    declared_market_context_sources: tuple[str, ...]
    completion_count_without_repair: int
    repair_used: bool


def collect_behavioral_trace(
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
    result: InvestmentAnswer,
    completion_count: int,
) -> BehavioralTrace:
    """从 Provider 请求而非 Final Sources 计算 Tool Trace 与 Repair。"""

    tool_tickers = tuple(market_data.requested_tickers)
    history_tickers = tuple(query.ticker for query in market_data.historical_queries)
    news_tickers = tuple(query.ticker for query in news.queries)
    retrieved_quote_sources = tuple(
        ticker
        for ticker, quote_result in market_data.quote_results
        if quote_result.status is MarketDataStatus.OK and quote_result.data is not None
    )
    retrieved_history_sources = tuple(
        query.ticker
        for query, history_result in market_data.historical_query_results
        if history_result.status is MarketDataStatus.OK and history_result.data is not None
    )
    retrieved_news_sources = tuple(
        query.ticker
        for query, news_result in news.query_results
        if news_result.status is NewsStatus.OK and news_result.data is not None
    )
    declared_quote_sources = _successful_source_tickers(
        result,
        ContextSourceType.CURRENT_QUOTE,
    )
    declared_history_sources = _successful_source_tickers(
        result,
        ContextSourceType.PRICE_HISTORY,
    )
    declared_news_sources = _successful_source_tickers(
        result,
        ContextSourceType.RECENT_NEWS,
    )
    retrieved_market_context_sources = (
        ("SPY",)
        if any(
            context_result.status is MarketDataStatus.OK and context_result.data is not None
            for context_result in market_context.results
        )
        else ()
    )
    declared_market_context_sources = _successful_source_tickers(
        result,
        ContextSourceType.MARKET_CONTEXT,
    )
    tool_round_used = bool(
        tool_tickers or history_tickers or news_tickers or market_context.request_count
    )
    completion_count_without_repair = 2 if tool_round_used else 1
    return BehavioralTrace(
        tool_tickers=tool_tickers,
        history_tickers=history_tickers,
        news_tickers=news_tickers,
        retrieved_quote_sources=retrieved_quote_sources,
        retrieved_history_sources=retrieved_history_sources,
        retrieved_news_sources=retrieved_news_sources,
        declared_quote_sources=declared_quote_sources,
        declared_history_sources=declared_history_sources,
        declared_news_sources=declared_news_sources,
        market_context_calls=market_context.request_count,
        retrieved_market_context_sources=retrieved_market_context_sources,
        declared_market_context_sources=declared_market_context_sources,
        completion_count_without_repair=completion_count_without_repair,
        repair_used=completion_count > completion_count_without_repair,
    )


def _successful_source_tickers(
    result: InvestmentAnswer,
    source_type: ContextSourceType,
) -> tuple[str, ...]:
    """只把 Final Sources 中 status=OK 的 Context 视为模型声明来源。"""

    return tuple(
        source.ticker
        for source in result.sources
        if source.type is source_type and source.status == "OK" and source.ticker is not None
    )


def structured_response_diagnostics(
    llm: CountingLLM,
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
) -> list[dict[str, object]]:
    """用本轮实际 Retrieved Context 诊断 Structured Completion。"""

    available_sources = _retrieved_source_references(market_data, news, market_context)
    diagnostics: list[dict[str, object]] = []
    for completion_index, result in enumerate(llm.results, start=1):
        if result.completion is None or result.completion.message.content is None:
            continue
        content = result.completion.message.content
        try:
            structured_answer = parse_structured_answer(content)
            validate_source_references(structured_answer, available_sources)
        except (InvalidStructuredAnswer, UnresolvedSourceReference) as error:
            diagnostics.append(
                {
                    "completion_index": completion_index,
                    "structured_answer_error": str(error),
                }
            )
            continue
        diagnostics.append(
            {
                "completion_index": completion_index,
                "answer": structured_answer.answer,
                "source_refs": [
                    {"type": reference.type.value, "ticker": reference.ticker}
                    for reference in structured_answer.source_refs
                ],
            }
        )
    return diagnostics


def _retrieved_source_references(
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
) -> tuple[SourceReference, ...]:
    """只从本轮实际请求且成功返回的 Context 构造可声明来源。"""

    references = [SourceReference(SourceReferenceType.PORTFOLIO_SNAPSHOT)]
    references.extend(
        SourceReference(SourceReferenceType.CURRENT_QUOTE, ticker)
        for ticker, result in market_data.quote_results
        if result.status is MarketDataStatus.OK and result.data is not None
    )
    references.extend(
        SourceReference(SourceReferenceType.PRICE_HISTORY, query.ticker)
        for query, result in market_data.historical_query_results
        if result.status is MarketDataStatus.OK and result.data is not None
    )
    references.extend(
        SourceReference(SourceReferenceType.RECENT_NEWS, query.ticker)
        for query, result in news.query_results
        if result.status is NewsStatus.OK and result.data is not None
    )
    if any(
        result.status is MarketDataStatus.OK and result.data is not None
        for result in market_context.results
    ):
        references.append(SourceReference(SourceReferenceType.MARKET_CONTEXT, "SPY"))
    return tuple(references)


def position(
    ticker: str,
    position_type: PositionType,
    shares: str,
    average_cost: str,
) -> Position:
    """创建固定 Evaluation Position。"""

    shares_value = Decimal(shares)
    average_cost_value = Decimal(average_cost)
    return Position(
        ticker=ticker,
        position_type=position_type,
        shares=shares_value,
        cost_basis=shares_value * average_cost_value,
        average_cost=average_cost_value,
    )


def fixed_quote(ticker: str, price: str) -> MarketDataResult[MarketQuote]:
    """创建不会随真实市场变化的 Current Quote。"""

    return MarketDataResult.success(
        MarketQuote(
            ticker=ticker,
            last_price=Decimal(price),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="FAKE_EVAL",
            feed="FIXED",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )
    )


def fixed_history(ticker: str) -> MarketDataResult[HistoricalBars]:
    """创建首尾上涨但不包含技术信号的固定 Daily History。"""

    return MarketDataResult.success(
        HistoricalBars(
            ticker=ticker,
            timeframe="1Day",
            bars=(
                OHLCVBar(
                    NOW - timedelta(days=2),
                    Decimal("198"),
                    Decimal("203"),
                    Decimal("197"),
                    Decimal("200"),
                    1000,
                ),
                OHLCVBar(
                    NOW - timedelta(days=1),
                    Decimal("203"),
                    Decimal("208"),
                    Decimal("202"),
                    Decimal("205"),
                    1100,
                ),
                OHLCVBar(
                    NOW,
                    Decimal("207"),
                    Decimal("212"),
                    Decimal("206"),
                    Decimal("210"),
                    1200,
                ),
            ),
            source="FAKE_EVAL",
            feed="FIXED",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            adjustment="ALL",
            fetched_at=NOW,
        )
    )


def fixed_news(ticker: str) -> NewsResult[RecentNews]:
    """创建不包含独立事实核验或因果结论的固定报道。"""

    return NewsResult.success(
        RecentNews(
            ticker=ticker,
            articles=(
                NewsArticle(
                    article_id="eval-news-1",
                    headline="Alphabet announces a product update",
                    summary="Benzinga reports details of an Alphabet product update.",
                    author="Fixed Reporter",
                    url="https://news.example.test/eval-news-1",
                    source="BENZINGA",
                    symbols=(ticker,),
                    created_at=NOW - timedelta(hours=3),
                    updated_at=NOW - timedelta(hours=2),
                ),
            ),
            provider="ALPACA",
            fetched_at=NOW,
        )
    )


def fixed_market_context(final_close: str) -> MarketDataResult[MarketRegimeContext]:
    """用可重复 SPY Daily Bars 创建确定性 Market Regime。"""

    closes = [Decimal("100"), Decimal("100")] + [Decimal(final_close)] * 19
    bars = tuple(
        OHLCVBar(
            NOW - timedelta(days=21 - index),
            close,
            close,
            close,
            close,
            10_000,
        )
        for index, close in enumerate(closes)
    )
    return MarketDataResult.success(
        calculate_market_regime(
            HistoricalBars(
                ticker="SPY",
                timeframe="1Day",
                bars=bars,
                source="FAKE_EVAL",
                feed="FIXED",
                coverage=MarketDataCoverage.CONSOLIDATED,
                currency="USD",
                adjustment="ALL",
                fetched_at=NOW,
            )
        )
    )


GOOG_LONG = position("GOOG", PositionType.LONG_TERM, "2", "200")
GOOG_SWING = position("GOOG", PositionType.SWING, "1", "220")
GOOG_LONG_PAIRED = position("GOOG", PositionType.LONG_TERM, "1", "210")
GOOG_SWING_PAIRED = position("GOOG", PositionType.SWING, "1", "210")
MSFT_LONG = position("MSFT", PositionType.LONG_TERM, "0.5", "450")
GOOG_QUOTE = fixed_quote("GOOG", "210.25")
MSFT_QUOTE = fixed_quote("MSFT", "500.50")
GOOG_HISTORY = fixed_history("GOOG")
GOOG_NEWS = fixed_news("GOOG")
NORMAL_MARKET_CONTEXT = fixed_market_context("100")
HIGH_STRESS_MARKET_CONTEXT = fixed_market_context("90")

CASES = (
    BehavioralCase(
        "add_existing_position",
        "我还有 300 美元，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "使用 300 美元现金、固定价格 210.25 和代码提供的关系",
            "区分长期仓和波段仓",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不将 Cash/Quote 数值关系解释为可以买入或至少可以买一股",
            "不自行计算可购买股数、剩余现金或碎股数量",
            "使用 NORMAL Market Regime，但不把 Heuristic 写成投资信号",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "current_price_without_position",
        "MSFT 现在多少钱？我目前有持仓吗？",
        Decimal("300"),
        (),
        {"MSFT": MSFT_QUOTE},
        ("MSFT",),
        InvestmentResponseStatus.OK,
        (
            "使用固定价格 500.50",
            "明确当前没有 MSFT 持仓",
            "不扩展用户未询问且 Asset Metadata 不支持的交易判断",
        ),
    ),
    BehavioralCase(
        "compare_two_quotes",
        "结合我目前的仓位，比较 GOOG 和 MSFT 现在的价格状态。",
        Decimal("300"),
        (GOOG_LONG, MSFT_LONG),
        {"GOOG": GOOG_QUOTE, "MSFT": MSFT_QUOTE},
        ("GOOG", "MSFT"),
        InvestmentResponseStatus.OK,
        (
            "两个 Quote 均来自 Fixed Tool Result",
            "只使用代码提供的 price_vs_average_cost 关系",
            "不自行生成跨 ticker 的绝对价格比较",
            "不将 Cash/Quote 数值关系解释为可以买入或无法买入",
            "不自行计算每股价差、盈亏金额或盈亏比例",
        ),
    ),
    BehavioralCase(
        "cash_only_no_tool",
        "我目前还有多少可用现金？",
        Decimal("175"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("回答 175", "不调用行情 Tool"),
    ),
    BehavioralCase(
        "positions_only_no_tool",
        "列出我现在的持仓类型和股数。",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "列出两类 GOOG Position",
            "不引用 Transaction History",
            "若说明合计股数，只使用 total_shares_by_ticker=3",
        ),
    ),
    BehavioralCase(
        "position_type_distinction",
        "我的 GOOG 长期仓和波段仓分别有多少股、平均成本多少？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("LONG_TERM 为 2 股/200", "SWING 为 1 股/220"),
    ),
    BehavioralCase(
        "missing_position_is_absence",
        "我现在有 NVDA 持仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("明确 NVDA 当前无持仓", "不要求用户补充已知 Portfolio"),
    ),
    BehavioralCase(
        "quote_no_data",
        "AMD 现在多少钱，我适合开始建仓吗？",
        Decimal("300"),
        (),
        {"AMD": MarketDataResult.failure(MarketDataStatus.NO_DATA, "固定无数据")},
        ("AMD",),
        InvestmentResponseStatus.DEGRADED,
        (
            "不编造 AMD 当前价格",
            "明确行情为 UNKNOWN",
            "仍使用固定 Market Context，但不据此替代缺失 Quote",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "quote_provider_failure",
        "TSLA 当前价格适合我加仓吗？",
        Decimal("100"),
        (),
        {
            "TSLA": MarketDataResult.failure(
                MarketDataStatus.PROVIDER_UNAVAILABLE,
                "固定 Provider Failure",
            )
        },
        ("TSLA",),
        InvestmentResponseStatus.DEGRADED,
        (
            "不编造 TSLA 当前价格",
            "使用 Market Context 与 100 美元现金安全降级",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "drop_reason_unknown",
        "GOOG 今天为什么跌？",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "调用 GOOG Recent News，且不机械调用 Current Quote 或 Price History",
            "将 Benzinga headline/summary 明确归因为来源报道，而非系统独立验证事实",
            "不确认用户前提中的今天下跌，因为缺少 intraday change",
            "只把报道与价格变化的关系表述为条件式 INFERENCE，不写成原因事实或唯一原因",
            "不因个股异动原因问题机械调用整体 Market Context",
        ),
        news_results={"GOOG": GOOG_NEWS},
        expected_news_tickers=("GOOG",),
    ),
    BehavioralCase(
        "post_earnings_unknown",
        "GOOG 最新财报以后我还应该继续持有吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "明确没有最新 Earnings 数据",
            "不编造最新财报数字或内容",
            "不使用训练知识冒充最新财报",
            "不因为出现 GOOG 而机械调用 Quote",
        ),
    ),
    BehavioralCase(
        "market_context_normal",
        "结合当前整体市场状态，我的 GOOG 今天应该加仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "调用 GOOG Quote 与固定 SPY Market Context",
            "使用 NORMAL Regime，但说明 SPY 仅为美国大盘股代理",
            "与 market_context_high_stress 使用完全相同的问题并形成可解释差异",
            "不把 NORMAL 直接等价为适合买入",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "market_context_high_stress",
        "结合当前整体市场状态，我的 GOOG 今天应该加仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "调用 GOOG Quote 与固定 SPY Market Context",
            "使用 HIGH_STRESS 及其原始指标，但说明 SPY 仅为美国大盘股代理",
            "明确阈值是未回测 V1 Heuristic，不是行业标准或投资信号",
            "与 market_context_normal 使用完全相同的问题并形成可解释差异",
            "不把 Market Regime 直接等价为 BUY / HOLD / SELL",
        ),
        market_context_result=HIGH_STRESS_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "low_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("25"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "显式使用 25 美元现金、固定价格 210.25 和 cash_vs_one_share_price.relation=BELOW",
            "与 high_cash_personalization 使用完全相同的问题并形成可解释差异",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不将 Cash/Quote 数值关系解释为可以买入或无法买入",
            "不判断 tradable、fractionable 或实际能否成交",
            "不自行计算具体可购买股数、金额或仓位影响",
            "只把 NORMAL Market Regime 作为 Context，不作为买入信号",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "high_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("800"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "显式使用 800 美元现金和 cash_vs_one_share_price.relation=ABOVE",
            "与 low_cash_personalization 使用完全相同的问题并形成可解释差异",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不将 Cash/Quote 数值关系解释为可以买入或至少可以买一股",
            "不自行计算可购买股数、剩余现金或交易后仓位比例",
            "只把 NORMAL Market Regime 作为 Context，不作为买入信号",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "long_term_position_personalization",
        "结合我的持仓类型，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_LONG_PAIRED,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "明确当前只有 1 股/成本 210 的 GOOG LONG_TERM 仓位",
            "与 swing_position_personalization 因 Position Type 不同形成可解释差异",
            "不将 Cash/Quote 数值关系解释为可以买入或至少可以买一股",
            "不使用略高、微利等未由代码提供的关系幅度",
            "不自行计算购买数量、剩余现金或新 Average Cost",
            "使用 NORMAL Market Regime，但不改变 LONG_TERM 语义",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "swing_position_personalization",
        "结合我的持仓类型，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_SWING_PAIRED,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "明确当前只有 1 股/成本 210 的 GOOG SWING 仓位",
            "与 long_term_position_personalization 因 Position Type 不同形成可解释差异",
            "说明交易计划、退出条件和风险预算未进入 Context",
            "不生成趋势、支撑、阻力、动能或震荡区间等技术分析",
            "不将 Cash/Quote 数值关系解释为可以买入或至少可以买一股",
            "不使用略高、微利等未由代码提供的关系幅度",
            "不自行计算购买数量、剩余现金、价差或新 Average Cost",
            "使用 NORMAL Market Regime，但不改变 SWING 语义",
        ),
        market_context_result=NORMAL_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "position_reduction_high_stress",
        "如果现在要减仓 GOOG，我应该先减波段仓还是长期仓？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "调用 GOOG Quote 与固定 HIGH_STRESS Market Context",
            "保留 LONG_TERM / SWING 独立语义，不把两类仓位聚合后决定卖出",
            "说明退出条件与交易计划仍为 UNKNOWN，不编造具体卖出数量",
            "Market Regime 只影响条件式风险分析，不直接产生 SELL 信号",
        ),
        market_context_result=HIGH_STRESS_MARKET_CONTEXT,
        expected_market_context_calls=1,
    ),
    BehavioralCase(
        "unspecified_ticker_no_tool",
        "只看我目前的持仓结构，我是否过度集中？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING, MSFT_LONG),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "使用 distinct_ticker_count=2 和代码提供的 GOOG 73.37%/MSFT 26.63% 历史成本权重",
            "保留 GOOG LONG_TERM / SWING 与 MSFT LONG_TERM 原始语义",
            "不使用不同 ticker 的股数大小比较集中度",
            "不把历史成本权重描述为 current market value allocation",
            "明确 current_market_value_weight 为 UNAVAILABLE",
            "不自行计算 available_cash_weight 或 total_portfolio_value",
            "不使用未提供的集中度阈值直接判定过度集中",
            "不推断 GOOG/MSFT 的行业关系或行业集中度",
            "不自行选择 Ticker 调用行情",
        ),
    ),
    BehavioralCase(
        "recent_price_history",
        "GOOG 最近一个月的价格路径如何？不要做技术分析。",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "调用 GOOG Price History Tool，且不调用 Current Quote",
            "使用首尾收盘价、区间高低、涨跌额、涨跌幅和 UP 方向",
            "不把最新历史收盘价描述为当前价格",
            "不生成移动平均、RSI、支撑阻力、技术信号或预测",
            "不解释价格变化原因",
        ),
        historical_results={"GOOG": GOOG_HISTORY},
        expected_history_tickers=("GOOG",),
    ),
    BehavioralCase(
        "recent_news",
        "GOOG 最近有什么新闻？只告诉我来源可追溯的报道。",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "只调用 GOOG Recent News",
            "明确使用 Alpaca 提供、Benzinga 署名的 attributed reporting",
            "使用“Benzinga 报道”而不是把 headline/summary 自动升级为确定事实",
            "不调用 Current Quote、Price History 或未提供的 Earnings",
            "不生成价格因果、预测或交易信号",
        ),
        news_results={"GOOG": GOOG_NEWS},
        expected_news_tickers=("GOOG",),
    ),
)


def test_tool_trace_source_declaration_and_repair_are_independent() -> None:
    """漏报 Quote / History Source 不得抹掉真实 Tool Trace 或伪造 Repair。"""

    market_data = FixedMarketData(
        {"GOOG": fixed_quote("GOOG", "210.25")},
        {"GOOG": fixed_history("GOOG")},
    )
    news = FixedNews({"GOOG": fixed_news("GOOG")})
    market_context = FixedMarketContext(NORMAL_MARKET_CONTEXT)
    market_data.get_current_quote("GOOG")
    market_data.get_historical_bars(HistoricalBarsQuery("GOOG", NOW - timedelta(days=5), NOW, 5))
    news.get_recent_news(NewsQuery("GOOG", NOW - timedelta(days=5), NOW, 5))
    result = InvestmentAnswer(
        InvestmentResponseStatus.OK,
        "模型只声明使用新闻。",
        (
            ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
            ContextSource(ContextSourceType.RECENT_NEWS, "OK", ticker="GOOG"),
        ),
    )

    trace = collect_behavioral_trace(
        market_data,
        news,
        market_context,
        result,
        completion_count=2,
    )

    assert trace.tool_tickers == ("GOOG",)
    assert trace.history_tickers == ("GOOG",)
    assert trace.news_tickers == ("GOOG",)
    assert trace.retrieved_quote_sources == ("GOOG",)
    assert trace.retrieved_history_sources == ("GOOG",)
    assert trace.retrieved_news_sources == ("GOOG",)
    assert trace.declared_quote_sources == ()
    assert trace.declared_history_sources == ()
    assert trace.declared_news_sources == ("GOOG",)
    assert trace.market_context_calls == 0
    assert trace.retrieved_market_context_sources == ()
    assert trace.declared_market_context_sources == ()
    assert trace.completion_count_without_repair == 2
    assert trace.repair_used is False


def test_diagnostics_only_accept_sources_retrieved_in_actual_tool_round() -> None:
    """Fixture 中存在但未 Retrieve 的 Quote 不得被 Diagnostics 当成可用 Source。"""

    market_data = FixedMarketData({"GOOG": fixed_quote("GOOG", "210.25")}, {})
    news = FixedNews({})
    market_context = FixedMarketContext(NORMAL_MARKET_CONTEXT)
    completion = LLMResult.success(
        LLMMessage(
            LLMRole.ASSISTANT,
            json.dumps(
                {
                    "answer": "GOOG 当前约为 210.25 USD。",
                    "source_refs": [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
                }
            ),
        )
    )
    llm = CountingLLM(NoopLLM(), results=[completion])

    before_retrieval = structured_response_diagnostics(
        llm,
        market_data,
        news,
        market_context,
    )
    market_data.get_current_quote("GOOG")
    after_retrieval = structured_response_diagnostics(
        llm,
        market_data,
        news,
        market_context,
    )

    assert "structured_answer_error" in before_retrieval[0]
    assert after_retrieval[0]["answer"] == "GOOG 当前约为 210.25 USD。"


def create_real_llm() -> AliyunLLMProvider:
    """只从显式 Process Environment 创建真实 Adapter，不读取仓库 .env。"""

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY 未配置")
    return AliyunLLMProvider(
        api_key=api_key,
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("LLM_MODEL", "qwen3.7-plus"),
        timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")),
    )


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv("RUN_REAL_LLM_BEHAVIORAL_EVAL") != "1",
    reason="需要显式启用真实模型 Behavioral Eval",
)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_real_model_behavior_with_fixed_market_data(case: BehavioralCase) -> None:
    """真实模型必须产生符合固定场景的 Tool Trace，并输出供 Human Review 的回答。"""

    llm = CountingLLM(create_real_llm())
    market_data = FixedMarketData(case.market_results, case.historical_results)
    news = FixedNews(case.news_results)
    market_context = FixedMarketContext(case.market_context_result)
    agent = InvestmentAgent(
        FixedPortfolioReader(case),
        market_data,
        llm,
        news=news,
        market_context=market_context,
        clock=lambda: NOW + timedelta(minutes=30),
    )

    result = agent.answer(USER_ID, case.question)

    if isinstance(result, InvestmentRequestFailure):
        pytest.fail(
            f"{case.id} 未形成 Final Answer: {result}\n"
            + json.dumps(
                {
                    "structured_response_diagnostics": structured_response_diagnostics(
                        llm,
                        market_data,
                        news,
                        market_context,
                    )
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    assert isinstance(result, InvestmentAnswer)
    trace = collect_behavioral_trace(
        market_data,
        news,
        market_context,
        result,
        llm.completion_count,
    )
    print(
        json.dumps(
            {
                "case": case.id,
                "question": case.question,
                "actual_tool_trace": {
                    "quote_tickers": trace.tool_tickers,
                    "history_tickers": trace.history_tickers,
                    "news_tickers": trace.news_tickers,
                    "market_context_calls": trace.market_context_calls,
                },
                "declared_final_sources": {
                    "quote_tickers": trace.declared_quote_sources,
                    "history_tickers": trace.declared_history_sources,
                    "news_tickers": trace.declared_news_sources,
                    "market_context_tickers": trace.declared_market_context_sources,
                },
                "retrieved_successful_contexts": {
                    "quote_tickers": trace.retrieved_quote_sources,
                    "history_tickers": trace.retrieved_history_sources,
                    "news_tickers": trace.retrieved_news_sources,
                    "market_context_tickers": trace.retrieved_market_context_sources,
                },
                "status": result.status.value,
                "llm_completion_count": llm.completion_count,
                "source_validation_repair_used": trace.repair_used,
                "answer": result.answer,
                "human_checks": case.human_checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    assert len(trace.tool_tickers) == len(case.expected_tickers)
    assert sorted(trace.tool_tickers) == sorted(case.expected_tickers)
    assert len(trace.history_tickers) == len(case.expected_history_tickers)
    assert sorted(trace.history_tickers) == sorted(case.expected_history_tickers)
    assert len(trace.news_tickers) == len(case.expected_news_tickers)
    assert sorted(trace.news_tickers) == sorted(case.expected_news_tickers)
    assert trace.market_context_calls == case.expected_market_context_calls
    assert result.status is case.expected_status
    assert llm.completion_count <= trace.completion_count_without_repair + 1
