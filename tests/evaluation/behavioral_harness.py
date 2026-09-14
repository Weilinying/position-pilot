"""Behavioral Evaluation 使用的固定 Provider、Trace 与 Fixture 辅助实现。"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from position_pilot.application.investment_agent import (
    ContextSourceType,
    InvestmentAnswer,
)
from position_pilot.application.investment_answer import (
    InvalidStructuredAnswer,
    SourceReference,
    SourceReferenceType,
    UnresolvedSourceReference,
    parse_structured_answer,
    validate_source_references,
)
from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponseFormat,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
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
    PortfolioState,
    Position,
    PositionType,
    Transaction,
    TransactionAction,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000101")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


class FixedPortfolioReader:
    """为真实模型提供显式传入、完整且可重复的 Portfolio Snapshot。"""

    def __init__(
        self,
        *,
        state: PortfolioState,
        transactions: tuple[Transaction, ...] = (),
    ) -> None:
        self._state = state
        self._transactions = transactions

    def get_investment_context(self, user_id: UUID) -> InvestmentPortfolioContext:
        """只为对应 Portfolio Owner 构造固定投资上下文。"""

        assert user_id == self._state.user_id
        return InvestmentPortfolioContext.from_ledger(self._state, self._transactions)


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
        """返回固定 Quote，并记录规范化后的 ticker。"""

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
        """返回固定历史行情，并记录完整查询参数。"""

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
        """返回固定新闻结果，并保留查询窗口。"""

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
        """返回固定 Market Context。"""

        self.request_count += 1
        self.results.append(self._result)
        return self._result


@dataclass(slots=True)
class CountingLLM:
    """记录 Behavioral Case 的 Completion 数，观察是否触发一次 Repair。"""

    delegate: LLMProvider
    completion_count: int = 0
    results: list[LLMResult] = field(default_factory=list)
    response_formats: list[LLMResponseFormat] = field(default_factory=list)
    routing_response_format_override: LLMResponseFormat | None = None

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """记录请求后委托给底层 LLM Provider。"""

        effective_response_format = (
            self.routing_response_format_override
            if tools and self.routing_response_format_override is not None
            else response_format
        )
        self.completion_count += 1
        self.response_formats.append(effective_response_format)
        result = self.delegate.complete(
            messages,
            tools=tools,
            response_format=effective_response_format,
        )
        self.results.append(result)
        return result


class NoopLLM:
    """Diagnostics 回归不应实际调用 Delegate。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """拒绝不应发生的真实模型调用。"""

        raise AssertionError("测试不应调用 NoopLLM")


@dataclass(slots=True)
class ResponseFormatRecordingLLM:
    """记录 Delegate 实际收到的 Response Format。"""

    response_formats: list[LLMResponseFormat] = field(default_factory=list)

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """记录格式并返回最小固定响应。"""

        self.response_formats.append(response_format)
        return LLMResult.success(LLMMessage(LLMRole.ASSISTANT, '{"answer":"ok"}'))


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
    quote_request_purposes: tuple[str, ...]
    model_selected_market_context: bool
    floor_added_market_context: bool


def collect_behavioral_trace(
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
    result: InvestmentAnswer,
    completion_count: int,
    routing_tool_calls: tuple[LLMToolCall, ...] = (),
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
    quote_request_purposes = tuple(
        purpose
        for tool_call in routing_tool_calls
        if tool_call.name == "get_current_quote"
        and isinstance((purpose := tool_call.arguments.get("request_purpose")), str)
    )
    model_selected_market_context = any(
        tool_call.name == "get_market_context" for tool_call in routing_tool_calls
    )
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
        quote_request_purposes=quote_request_purposes,
        model_selected_market_context=model_selected_market_context,
        floor_added_market_context=(
            market_context.request_count > 0 and not model_selected_market_context
        ),
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
        if result.completion is None:
            continue
        message = result.completion.message
        # 首轮带 tool_calls 的消息是 Routing Completion，不属于 Final JSON Contract。
        if message.tool_calls or message.content is None:
            continue
        content = message.content
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


def behavioral_completion_metrics(
    llm: CountingLLM,
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
) -> dict[str, object]:
    """汇总 JSON、Source Validation、Repair 与 Provider Timeout 诊断。"""

    available_sources = _retrieved_source_references(market_data, news, market_context)
    invalid_json_count = 0
    structured_contract_failure_count = 0
    source_validation_failure_count = 0
    provider_timeout_count = 0
    for result in llm.results:
        if result.status is LLMStatus.PROVIDER_UNAVAILABLE and result.error_message is not None:
            provider_timeout_count += int("超时" in result.error_message)
        if result.completion is None:
            continue
        message = result.completion.message
        # Routing Completion 可能同时携带 content；只有无 tool_calls 的 Final/Repair
        # Completion 才进入 JSON、Structured Contract 与 Source Validation 指标。
        if message.tool_calls or message.content is None:
            continue
        content = message.content
        try:
            json.loads(content)
        except json.JSONDecodeError:
            invalid_json_count += 1
        try:
            structured_answer = parse_structured_answer(content)
        except InvalidStructuredAnswer:
            structured_contract_failure_count += 1
            continue
        try:
            validate_source_references(structured_answer, available_sources)
        except UnresolvedSourceReference:
            source_validation_failure_count += 1
    expected_completion_count = (
        2
        if (
            market_data.requested_tickers
            or market_data.historical_queries
            or news.queries
            or market_context.request_count
        )
        else 1
    )
    repair_count = max(llm.completion_count - expected_completion_count, 0)
    return {
        "invalid_json_count": invalid_json_count,
        "structured_contract_failure_count": structured_contract_failure_count,
        "source_validation_failure_count": source_validation_failure_count,
        "repair_count": repair_count,
        "case_used_repair": repair_count > 0,
        "provider_timeout_count": provider_timeout_count,
        "response_formats": [response_format.value for response_format in llm.response_formats],
    }


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


def fixed_buy(
    sequence: int,
    ticker: str,
    position_type: PositionType,
    price: str,
    shares: str,
    *,
    days_ago: int,
) -> Transaction:
    """创建 Behavioral Eval 使用的固定历史 BUY。"""

    return Transaction.create(
        user_id=USER_ID,
        sequence=sequence,
        ticker=ticker,
        action=TransactionAction.BUY,
        price=Decimal(price),
        shares=Decimal(shares),
        position_type=position_type,
        occurred_at=NOW - timedelta(days=days_ago),
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


def collect_failure_execution_trace(
    llm: CountingLLM,
    market_data: FixedMarketData,
    news: FixedNews,
    market_context: FixedMarketContext,
) -> dict[str, object]:
    """从 Evaluation Fake 记录提取 Request Failure 前的实际 Tool Trace。"""

    routing_tool_calls = (
        llm.results[0].completion.message.tool_calls
        if llm.results and llm.results[0].completion is not None
        else ()
    )
    return {
        "model_tool_calls": [
            {"name": tool_call.name, "arguments": tool_call.arguments}
            for tool_call in routing_tool_calls
        ],
        "tool_attempts": [
            *(
                {
                    "name": "get_current_quote",
                    "ticker": ticker,
                    "status": result.status.value,
                }
                for ticker, result in market_data.quote_results
            ),
            *(
                {
                    "name": "get_recent_price_history",
                    "ticker": query.ticker,
                    "status": result.status.value,
                }
                for query, result in market_data.historical_query_results
            ),
            *(
                {
                    "name": "get_recent_news",
                    "ticker": query.ticker,
                    "status": result.status.value,
                }
                for query, result in news.query_results
            ),
            *(
                {
                    "name": "get_market_context",
                    "ticker": "SPY",
                    "status": result.status.value,
                }
                for result in market_context.results
            ),
        ],
    }


__all__ = [
    "NOW",
    "USER_ID",
    "BehavioralTrace",
    "CountingLLM",
    "FixedMarketContext",
    "FixedMarketData",
    "FixedNews",
    "FixedPortfolioReader",
    "NoopLLM",
    "ResponseFormatRecordingLLM",
    "behavioral_completion_metrics",
    "collect_behavioral_trace",
    "collect_failure_execution_trace",
    "fixed_buy",
    "fixed_history",
    "fixed_market_context",
    "fixed_news",
    "fixed_quote",
    "position",
    "structured_response_diagnostics",
]
