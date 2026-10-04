"""现有只读金融 Tool 的 Application-owned 执行边界。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from position_pilot.application.llm import LLMToolCall
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.news_service import NewsQuery
from position_pilot.domain.market_context import MarketRegimeContext
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.news import NewsResult, NewsStatus, RecentNews

CURRENT_QUOTE_TOOL_NAME = "get_current_quote"
RECENT_PRICE_HISTORY_TOOL_NAME = "get_recent_price_history"
RECENT_NEWS_TOOL_NAME = "get_recent_news"
MARKET_CONTEXT_TOOL_NAME = "get_market_context"
PRICE_HISTORY_LOOKBACK_DAYS = 45
PRICE_HISTORY_LIMIT = 30
PRICE_HISTORY_END_LAG = timedelta(minutes=15)
NEWS_LOOKBACK_DAYS = 5
NEWS_LIMIT = 5
NEWS_END_LAG = timedelta(minutes=15)

type FinancialToolResult = (
    MarketDataResult[MarketQuote]
    | MarketDataResult[HistoricalBars]
    | NewsResult[RecentNews]
    | MarketDataResult[MarketRegimeContext]
)


class FinancialMarketDataReader(Protocol):
    """Quote 与 Price History 的最小执行接口。"""

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]: ...

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]: ...


class FinancialNewsReader(Protocol):
    """Recent News 的最小执行接口。"""

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]: ...


class FinancialMarketContextReader(Protocol):
    """Market Context 的最小执行接口。"""

    def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]: ...


class InvalidFinancialToolResult(ValueError):
    """Provider 明确返回无效 Tool Arguments 对应状态。"""


@dataclass(frozen=True, slots=True)
class FinancialToolExecution:
    """一次 Tool Call 的原始结果与去重信息。"""

    tool_call: LLMToolCall
    result: FinancialToolResult
    normalized_ticker: str | None
    is_duplicate: bool

    @property
    def succeeded(self) -> bool:
        """统一判断 Market Data 与 News 的成功状态。"""

        return self.result.status.value == "OK"


class FinancialToolExecutor:
    """执行、固定窗口并去重当前四个只读金融 Tool。"""

    def __init__(
        self,
        market_data: FinancialMarketDataReader,
        news: FinancialNewsReader,
        market_context: FinancialMarketContextReader,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._market_data = market_data
        self._news = news
        self._market_context = market_context
        self._clock = clock
        self._quotes: dict[str, MarketDataResult[MarketQuote]] = {}
        self._history: dict[str, MarketDataResult[HistoricalBars]] = {}
        self._news_results: dict[str, NewsResult[RecentNews]] = {}
        self._market_context_result: MarketDataResult[MarketRegimeContext] | None = None
        self._market_context_failed = False
        self._provider_fetch_count = 0

    @property
    def provider_fetch_count(self) -> int:
        """记录本轮真实 Provider 请求，包含返回无效标的的请求。"""

        return self._provider_fetch_count

    @property
    def unique_execution_count(self) -> int:
        """返回本轮实际访问 Provider 的唯一 Tool 数量。"""

        return (
            len(self._quotes)
            + len(self._history)
            + len(self._news_results)
            + int(self._market_context_result is not None)
        )

    def execute(self, tool_call: LLMToolCall) -> FinancialToolExecution:
        """按 Tool Contract 执行调用，并复用同一轮已取得的相同结果。"""

        if tool_call.name == MARKET_CONTEXT_TOOL_NAME:
            if self._market_context_failed:
                raise RuntimeError("MARKET_CONTEXT_PROVIDER_FAILURE")
            duplicate = self._market_context_result is not None
            if self._market_context_result is None:
                self._provider_fetch_count += 1
                try:
                    self._market_context_result = self._market_context.get_current_market_context()
                except Exception:  # noqa: BLE001 - 同轮复用明确失败，不重复请求 Provider。
                    self._market_context_failed = True
                    raise
            return FinancialToolExecution(
                tool_call,
                self._market_context_result,
                None,
                duplicate,
            )

        ticker = tool_call.arguments["ticker"]
        assert isinstance(ticker, str)
        normalized = ticker.strip().upper()
        if tool_call.name == CURRENT_QUOTE_TOOL_NAME:
            duplicate = normalized in self._quotes
            quote_result = self._quotes.get(normalized)
            if quote_result is None:
                self._provider_fetch_count += 1
                quote_result = self._market_data.get_current_quote(normalized)
                if quote_result.status in {
                    MarketDataStatus.INVALID_SYMBOL,
                    MarketDataStatus.INVALID_REQUEST,
                }:
                    raise InvalidFinancialToolResult(f"{CURRENT_QUOTE_TOOL_NAME} ticker 参数无效")
                self._quotes[normalized] = quote_result
            return FinancialToolExecution(tool_call, quote_result, normalized, duplicate)
        if tool_call.name == RECENT_PRICE_HISTORY_TOOL_NAME:
            duplicate = normalized in self._history
            history_result = self._history.get(normalized)
            if history_result is None:
                self._provider_fetch_count += 1
                history_result = self._market_data.get_historical_bars(
                    self._recent_price_history_query(normalized)
                )
                if history_result.status is MarketDataStatus.INVALID_SYMBOL:
                    raise InvalidFinancialToolResult(
                        f"{RECENT_PRICE_HISTORY_TOOL_NAME} ticker 参数无效"
                    )
                self._history[normalized] = history_result
            return FinancialToolExecution(tool_call, history_result, normalized, duplicate)
        if tool_call.name == RECENT_NEWS_TOOL_NAME:
            duplicate = normalized in self._news_results
            news_result = self._news_results.get(normalized)
            if news_result is None:
                self._provider_fetch_count += 1
                news_result = self._news.get_recent_news(self._recent_news_query(normalized))
                if news_result.status is NewsStatus.INVALID_SYMBOL:
                    raise InvalidFinancialToolResult(f"{RECENT_NEWS_TOOL_NAME} ticker 参数无效")
                self._news_results[normalized] = news_result
            return FinancialToolExecution(tool_call, news_result, normalized, duplicate)
        raise ValueError(f"未知 Financial Tool: {tool_call.name}")

    def _recent_price_history_query(self, ticker: str) -> HistoricalBarsQuery:
        end = self._utc_now() - PRICE_HISTORY_END_LAG
        return HistoricalBarsQuery(
            ticker=ticker,
            start=end - timedelta(days=PRICE_HISTORY_LOOKBACK_DAYS),
            end=end,
            limit=PRICE_HISTORY_LIMIT,
        )

    def _recent_news_query(self, ticker: str) -> NewsQuery:
        end = self._utc_now() - NEWS_END_LAG
        return NewsQuery(
            ticker=ticker,
            start=end - timedelta(days=NEWS_LOOKBACK_DAYS),
            end=end,
            limit=NEWS_LIMIT,
        )

    def _utc_now(self) -> datetime:
        current_time = self._clock()
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise RuntimeError("InvestmentAgent clock 必须返回含时区的 datetime")
        return current_time.astimezone(UTC)
