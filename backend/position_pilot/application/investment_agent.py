"""M3 Single Investment Agent 与受限 Native Function Calling。"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import monotonic
from typing import Protocol
from uuid import UUID

from position_pilot.application.investment_context import (
    M3_CONTEXT_CAPABILITIES,
    PortfolioSnapshot,
    QuoteDerivedFacts,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
)
from position_pilot.domain.market_data import MarketDataResult, MarketDataStatus, MarketQuote
from position_pilot.domain.portfolio import PortfolioState

LOGGER = logging.getLogger(__name__)
CURRENT_QUOTE_TOOL_NAME = "get_current_quote"
MAX_TOOL_CALLS_PER_ROUND = 3
MAX_QUESTION_LENGTH = 4_000

SYSTEM_PROMPT = "\n".join(
    (
        "你是 PositionPilot 的 Single Investment Agent。",
        "1. 只能使用 Structured Facts、Tool Results 和 Deterministic Derived Facts。",
        "2. 不得自行生成未提供的确定性金融计算结果；缺失结果必须保持 UNKNOWN。",
        "3. 分析必须服从 Context Capabilities；UNAVAILABLE 或 UNKNOWN 不得用训练知识补足。",
        "Context Capability 只表示某类数据来源是否可用，不表示具体 ticker 的属性或状态。",
        "4. Portfolio positions 是完整当前持仓集合；缺少 ticker 表示当前无该持仓。",
        "必须保留 LONG_TERM / SWING 语义，不得让 ticker 聚合覆盖 Position Type。",
        "5. 问题需要当前 Quote 这一证据时才调用 get_current_quote；Quote 不能解释异动原因。",
        "6. 当前价格只来自成功 Tool Result；Tool Failure 或缺失 Context 必须明确为 UNKNOWN。",
        "7. 回答自然地区分事实、推断和未知信息，不要求固定标题。",
        "禁止示例：cash=300 且 price=210.25，就自行声称可买 1 股、剩余 89.75。",
        "允许示例：若 executable_purchase_quantity 未提供，明确实际可执行购买数量未知。",
    )
)

CURRENT_QUOTE_TOOL = LLMToolDefinition(
    name=CURRENT_QUOTE_TOOL_NAME,
    description="获取美股或美国上市 ETF 的当前 Quote；只有问题需要当前价格时才调用。",
    parameters={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "需要 Current Quote 的美股或美国上市 ETF ticker",
            }
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
)


class PortfolioSnapshotReader(Protocol):
    """Agent 读取当前完整 Portfolio State 的最小接口。"""

    def get_portfolio(self, user_id: UUID) -> PortfolioState: ...


class CurrentQuoteReader(Protocol):
    """Agent 执行 Current Quote Tool 的最小接口。"""

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]: ...


class InvestmentResponseStatus(StrEnum):
    """由确定性 Tool Result 计算的成功响应状态。"""

    OK = "OK"
    DEGRADED = "DEGRADED"


class InvestmentFailureCode(StrEnum):
    """无法形成 Final Answer 的稳定 Request Failure。"""

    INVALID_QUESTION = "INVALID_QUESTION"
    INVALID_TOOL_CALL = "INVALID_TOOL_CALL"
    TOOL_CALL_LIMIT_EXCEEDED = "TOOL_CALL_LIMIT_EXCEEDED"
    TOOL_ROUND_LIMIT_EXCEEDED = "TOOL_ROUND_LIMIT_EXCEEDED"
    LLM_INVALID_REQUEST = "LLM_INVALID_REQUEST"
    LLM_AUTHENTICATION_FAILED = "LLM_AUTHENTICATION_FAILED"
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"
    LLM_PROVIDER_UNAVAILABLE = "LLM_PROVIDER_UNAVAILABLE"
    LLM_INVALID_PROVIDER_RESPONSE = "LLM_INVALID_PROVIDER_RESPONSE"


class ContextSourceType(StrEnum):
    """Final Answer 可追溯的事实来源类别。"""

    PORTFOLIO_SNAPSHOT = "PORTFOLIO_SNAPSHOT"
    CURRENT_QUOTE = "CURRENT_QUOTE"


@dataclass(frozen=True, slots=True)
class ContextSource:
    """Final Answer 使用的结构化事实来源与状态。"""

    type: ContextSourceType
    status: str
    ticker: str | None = None
    provider: str | None = None
    feed: str | None = None
    market_timestamp: datetime | None = None
    fetched_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class InvestmentAnswer:
    """包含确定性状态和来源追踪的 Final Answer。"""

    status: InvestmentResponseStatus
    answer: str
    sources: tuple[ContextSource, ...]


@dataclass(frozen=True, slots=True)
class InvestmentRequestFailure:
    """LLM 或 Agent Contract 无法形成 Final Answer。"""

    code: InvestmentFailureCode
    message: str


type InvestmentAgentResult = InvestmentAnswer | InvestmentRequestFailure


class InvestmentAgent:
    """协调 Portfolio Snapshot、Native Tool Call 与 Final Response。"""

    def __init__(
        self,
        portfolio_reader: PortfolioSnapshotReader,
        market_data: CurrentQuoteReader,
        llm_provider: LLMProvider,
    ) -> None:
        self._portfolio_reader = portfolio_reader
        self._market_data = market_data
        self._llm_provider = llm_provider

    def answer(self, user_id: UUID, question: str) -> InvestmentAgentResult:
        """执行最多一个 Tool Round，并返回 Answer 或明确 Request Failure。"""

        normalized_question = question.strip() if isinstance(question, str) else ""
        if not normalized_question or len(normalized_question) > MAX_QUESTION_LENGTH:
            return InvestmentRequestFailure(
                InvestmentFailureCode.INVALID_QUESTION,
                f"question 必须包含 1 到 {MAX_QUESTION_LENGTH} 个字符",
            )

        started_at = monotonic()
        portfolio = self._portfolio_reader.get_portfolio(user_id)
        snapshot = PortfolioSnapshot.from_state(portfolio)
        sources: list[ContextSource] = [
            ContextSource(
                ContextSourceType.PORTFOLIO_SNAPSHOT,
                InvestmentResponseStatus.OK.value,
            )
        ]
        initial_messages = self._initial_messages(snapshot, normalized_question)
        LOGGER.info(
            "investment_agent_context_ready",
            extra={"position_count": len(snapshot.positions), "tool_count": 1},
        )

        first_result = self._llm_provider.complete(
            initial_messages,
            tools=(CURRENT_QUOTE_TOOL,),
        )
        first_failure = self._from_llm_failure(first_result)
        if first_failure is not None:
            self._log_failure(first_failure, started_at)
            return first_failure
        first_message = self._completion_message(first_result)

        if not first_message.tool_calls:
            answer = InvestmentAnswer(
                InvestmentResponseStatus.OK,
                self._require_final_content(first_message),
                tuple(sources),
            )
            self._log_success(answer, started_at, tool_call_count=0)
            return answer

        tool_call_failure = self._validate_tool_calls(first_message.tool_calls)
        if tool_call_failure is not None:
            self._log_failure(tool_call_failure, started_at)
            return tool_call_failure

        tool_messages: list[LLMMessage] = []
        market_results_by_ticker: dict[str, MarketDataResult[MarketQuote]] = {}
        degraded = False
        for tool_call in first_message.tool_calls:
            ticker = tool_call.arguments["ticker"]
            assert isinstance(ticker, str)
            normalized_ticker = ticker.strip().upper()
            is_duplicate = normalized_ticker in market_results_by_ticker
            if is_duplicate:
                market_result = market_results_by_ticker[normalized_ticker]
            else:
                market_result = self._market_data.get_current_quote(normalized_ticker)
                if market_result.status in {
                    MarketDataStatus.INVALID_SYMBOL,
                    MarketDataStatus.INVALID_REQUEST,
                }:
                    failure = InvestmentRequestFailure(
                        InvestmentFailureCode.INVALID_TOOL_CALL,
                        f"{CURRENT_QUOTE_TOOL_NAME} ticker 参数无效",
                    )
                    self._log_failure(failure, started_at)
                    return failure
                market_results_by_ticker[normalized_ticker] = market_result
            tool_message, source = self._market_tool_result(
                tool_call,
                market_result,
                snapshot,
            )
            tool_messages.append(tool_message)
            if is_duplicate:
                LOGGER.info(
                    "investment_agent_tool_deduplicated",
                    extra={
                        "tool_name": CURRENT_QUOTE_TOOL_NAME,
                        "ticker": normalized_ticker,
                    },
                )
            else:
                sources.append(source)
                degraded = degraded or market_result.status is not MarketDataStatus.OK
                LOGGER.info(
                    "investment_agent_tool_completed",
                    extra={
                        "tool_name": CURRENT_QUOTE_TOOL_NAME,
                        "ticker": source.ticker,
                        "tool_status": market_result.status.value,
                    },
                )

        final_result = self._llm_provider.complete(
            (*initial_messages, first_message, *tool_messages),
            tools=(),
        )
        final_failure = self._from_llm_failure(final_result)
        if final_failure is not None:
            self._log_failure(final_failure, started_at)
            return final_failure
        final_message = self._completion_message(final_result)
        if final_message.tool_calls:
            failure = InvestmentRequestFailure(
                InvestmentFailureCode.TOOL_ROUND_LIMIT_EXCEEDED,
                "Tool Result 返回后必须生成 Final Response",
            )
            self._log_failure(failure, started_at)
            return failure

        answer = InvestmentAnswer(
            InvestmentResponseStatus.DEGRADED if degraded else InvestmentResponseStatus.OK,
            self._require_final_content(final_message),
            tuple(sources),
        )
        self._log_success(
            answer,
            started_at,
            tool_call_count=len(market_results_by_ticker),
        )
        return answer

    @staticmethod
    def _initial_messages(
        snapshot: PortfolioSnapshot,
        question: str,
    ) -> tuple[LLMMessage, ...]:
        content = json.dumps(
            {
                "question": question,
                "context_capabilities": M3_CONTEXT_CAPABILITIES.as_dict(),
                "portfolio_snapshot": snapshot.as_dict(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return (
            LLMMessage(LLMRole.SYSTEM, SYSTEM_PROMPT),
            LLMMessage(LLMRole.USER, content),
        )

    @staticmethod
    def _validate_tool_calls(
        tool_calls: tuple[LLMToolCall, ...],
    ) -> InvestmentRequestFailure | None:
        if len(tool_calls) > MAX_TOOL_CALLS_PER_ROUND:
            return InvestmentRequestFailure(
                InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED,
                f"每个 Tool Round 最多允许 {MAX_TOOL_CALLS_PER_ROUND} 个调用",
            )
        for tool_call in tool_calls:
            if tool_call.name != CURRENT_QUOTE_TOOL_NAME:
                return InvestmentRequestFailure(
                    InvestmentFailureCode.INVALID_TOOL_CALL,
                    "模型请求了未授权 Tool",
                )
            if set(tool_call.arguments) != {"ticker"}:
                return InvestmentRequestFailure(
                    InvestmentFailureCode.INVALID_TOOL_CALL,
                    "get_current_quote arguments 必须只包含 ticker",
                )
            ticker = tool_call.arguments.get("ticker")
            if not isinstance(ticker, str) or not ticker.strip():
                return InvestmentRequestFailure(
                    InvestmentFailureCode.INVALID_TOOL_CALL,
                    "get_current_quote ticker 必须是非空字符串",
                )
        return None

    @staticmethod
    def _market_tool_result(
        tool_call: LLMToolCall,
        result: MarketDataResult[MarketQuote],
        snapshot: PortfolioSnapshot,
    ) -> tuple[LLMMessage, ContextSource]:
        if result.status is MarketDataStatus.OK:
            quote = result.data
            assert quote is not None
            payload: dict[str, object] = {
                "status": result.status.value,
                "current_market_fact_available": True,
                "ticker": quote.ticker,
                "last_price": str(quote.last_price),
                "bid_price": str(quote.bid_price) if quote.bid_price is not None else None,
                "ask_price": str(quote.ask_price) if quote.ask_price is not None else None,
                "last_trade_at": quote.last_trade_at.isoformat(),
                "quote_at": quote.quote_at.isoformat() if quote.quote_at else None,
                "source": quote.source,
                "feed": quote.feed,
                "coverage": quote.coverage.value,
                "currency": quote.currency,
                "is_delayed": quote.is_delayed,
                "fetched_at": quote.fetched_at.isoformat(),
                "deterministic_derived_facts": QuoteDerivedFacts.from_quote(
                    snapshot,
                    quote,
                ).as_dict(),
            }
            source = ContextSource(
                type=ContextSourceType.CURRENT_QUOTE,
                status=result.status.value,
                ticker=quote.ticker,
                provider=quote.source,
                feed=quote.feed,
                market_timestamp=quote.last_trade_at,
                fetched_at=quote.fetched_at,
            )
        else:
            ticker = tool_call.arguments["ticker"]
            assert isinstance(ticker, str)
            payload = {
                "status": result.status.value,
                "current_market_fact_available": False,
                "ticker": ticker.strip().upper(),
                "message": result.message,
                "instruction": "将当前行情视为 UNKNOWN，不得补造价格。",
            }
            source = ContextSource(
                type=ContextSourceType.CURRENT_QUOTE,
                status=result.status.value,
                ticker=ticker.strip().upper(),
            )
        return (
            LLMMessage(
                LLMRole.TOOL,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                tool_call_id=tool_call.id,
            ),
            source,
        )

    @staticmethod
    def _from_llm_failure(result: LLMResult) -> InvestmentRequestFailure | None:
        if result.status is LLMStatus.OK:
            return None
        code_by_status = {
            LLMStatus.INVALID_REQUEST: InvestmentFailureCode.LLM_INVALID_REQUEST,
            LLMStatus.AUTHENTICATION_FAILED: (InvestmentFailureCode.LLM_AUTHENTICATION_FAILED),
            LLMStatus.RATE_LIMITED: InvestmentFailureCode.LLM_RATE_LIMITED,
            LLMStatus.PROVIDER_UNAVAILABLE: (InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE),
            LLMStatus.INVALID_PROVIDER_RESPONSE: (
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE
            ),
        }
        return InvestmentRequestFailure(
            code_by_status[result.status],
            result.error_message or "LLM Provider 调用失败",
        )

    @staticmethod
    def _completion_message(result: LLMResult) -> LLMMessage:
        assert result.completion is not None
        return result.completion.message

    @staticmethod
    def _require_final_content(message: LLMMessage) -> str:
        if message.content is None:
            # LLMMessage 已保证无 Tool Call 时必须存在 content，此分支只保护未来修改。
            raise RuntimeError("Final Response 缺少 content")
        return message.content

    @staticmethod
    def _log_success(
        answer: InvestmentAnswer,
        started_at: float,
        *,
        tool_call_count: int,
    ) -> None:
        LOGGER.info(
            "investment_agent_completed",
            extra={
                "response_status": answer.status.value,
                "tool_call_count": tool_call_count,
                "latency_ms": round((monotonic() - started_at) * 1000, 2),
            },
        )

    @staticmethod
    def _log_failure(failure: InvestmentRequestFailure, started_at: float) -> None:
        LOGGER.warning(
            "investment_agent_failed",
            extra={
                "failure_code": failure.code.value,
                "latency_ms": round((monotonic() - started_at) * 1000, 2),
            },
        )
