"""InvestmentAgent 确定性 Orchestration 测试。"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.investment_agent import (
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
)
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakePortfolioReader:
    """返回固定完整 Portfolio State，并记录读取。"""

    state: PortfolioState
    requested_user_ids: list[UUID] = field(default_factory=list)

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        self.requested_user_ids.append(user_id)
        return self.state


@dataclass(slots=True)
class FakeMarketData:
    """按 Ticker 返回固定 Current Quote Result。"""

    results: dict[str, MarketDataResult[MarketQuote]]
    requested_tickers: list[str] = field(default_factory=list)

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        self.requested_tickers.append(ticker)
        return self.results.get(
            ticker.strip().upper(),
            MarketDataResult.failure(MarketDataStatus.NO_DATA, "测试无行情"),
        )


@dataclass(frozen=True, slots=True)
class RecordedCompletion:
    messages: tuple[LLMMessage, ...]
    tools: tuple[LLMToolDefinition, ...]


@dataclass(slots=True)
class ScriptedLLM:
    """按顺序返回固定 Completion，只用于验证 Agent Orchestration。"""

    results: list[LLMResult]
    completions: list[RecordedCompletion] = field(default_factory=list)

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
    ) -> LLMResult:
        self.completions.append(RecordedCompletion(messages, tools))
        return self.results.pop(0)


def make_portfolio(*, available_cash: str = "300") -> PortfolioState:
    """创建同时包含长期仓和波段仓的固定 Snapshot。"""

    return PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(
            user_id=USER_ID,
            initial_cash=Decimal("1000"),
            available_cash=Decimal(available_cash),
        ),
        positions=(
            Position(
                ticker="GOOG",
                position_type=PositionType.LONG_TERM,
                shares=Decimal("2"),
                cost_basis=Decimal("400"),
                average_cost=Decimal("200"),
            ),
            Position(
                ticker="GOOG",
                position_type=PositionType.SWING,
                shares=Decimal("1"),
                cost_basis=Decimal("220"),
                average_cost=Decimal("220"),
            ),
        ),
        transaction_count=8,
    )


def quote(ticker: str, price: str) -> MarketDataResult[MarketQuote]:
    """创建带固定 Source / Timestamp 的成功 Quote。"""

    return MarketDataResult.success(
        MarketQuote(
            ticker=ticker,
            last_price=Decimal(price),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="ALPACA",
            feed="IEX",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )
    )


def tool_message(*calls: tuple[str, str]) -> LLMResult:
    """创建包含一个或多个 Current Quote Call 的 Fake Completion。"""

    return LLMResult.success(
        LLMMessage(
            LLMRole.ASSISTANT,
            None,
            tuple(
                LLMToolCall(call_id, "get_current_quote", {"ticker": ticker})
                for call_id, ticker in calls
            ),
        )
    )


def final_message(content: str = "基于当前已知事实的回答") -> LLMResult:
    """创建 Fake Final Completion。"""

    return LLMResult.success(LLMMessage(LLMRole.ASSISTANT, content))


def make_agent(
    llm_results: list[LLMResult],
    *,
    market_results: dict[str, MarketDataResult[MarketQuote]] | None = None,
    portfolio: PortfolioState | None = None,
) -> tuple[InvestmentAgent, FakePortfolioReader, FakeMarketData, ScriptedLLM]:
    """组装完全不依赖真实 Provider 的 Agent。"""

    portfolio_reader = FakePortfolioReader(portfolio or make_portfolio())
    market_data = FakeMarketData(market_results or {})
    llm = ScriptedLLM(llm_results)
    return (
        InvestmentAgent(portfolio_reader, market_data, llm),
        portfolio_reader,
        market_data,
        llm,
    )


def assert_answer(result: InvestmentAnswer | InvestmentRequestFailure) -> InvestmentAnswer:
    """缩窄测试中的 Agent Result 类型。"""

    assert isinstance(result, InvestmentAnswer)
    return result


def assert_failure(
    result: InvestmentAnswer | InvestmentRequestFailure,
) -> InvestmentRequestFailure:
    """缩窄测试中的 Request Failure 类型。"""

    assert isinstance(result, InvestmentRequestFailure)
    return result


def test_always_injects_complete_portfolio_snapshot_without_transaction_history() -> None:
    """Snapshot 必须声明完整持仓集合，且 M3 不默认注入 Transaction History。"""

    agent, portfolio_reader, market_data, llm = make_agent([final_message()])

    result = assert_answer(agent.answer(USER_ID, "我现在有哪些持仓？"))

    user_content = llm.completions[0].messages[1].content
    assert user_content is not None
    payload = json.loads(user_content)
    snapshot = payload["portfolio_snapshot"]
    assert snapshot["positions_are_complete_current_set"] is True
    assert snapshot["missing_ticker_means_no_current_position"] is True
    assert "transactions" not in snapshot
    assert snapshot["available_cash"] == "300"
    assert [position["position_type"] for position in snapshot["positions"]] == [
        "LONG_TERM",
        "SWING",
    ]
    system_prompt = llm.completions[0].messages[0].content
    assert system_prompt is not None
    assert "tradable" in system_prompt
    assert "fractionable" in system_prompt
    assert "当前均为 UNKNOWN" in system_prompt
    assert "不得自行假设只能整股交易" in system_prompt
    assert "具体可购买股数必须由确定性代码计算" in system_prompt
    assert portfolio_reader.requested_user_ids == [USER_ID]
    assert market_data.requested_tickers == []
    assert result.status is InvestmentResponseStatus.OK
    assert result.sources[0].type is ContextSourceType.PORTFOLIO_SNAPSHOT


def test_no_tool_call_returns_ok_without_mechanical_market_request() -> None:
    """模型直接回答 Portfolio 问题时，Agent 不应机械调用 Market Tool。"""

    agent, _, market_data, llm = make_agent([final_message("可用现金为 300")])

    result = assert_answer(agent.answer(USER_ID, "我还有多少可用现金？"))

    assert result.status is InvestmentResponseStatus.OK
    assert result.answer == "可用现金为 300"
    assert market_data.requested_tickers == []
    assert len(llm.completions) == 1
    assert [tool.name for tool in llm.completions[0].tools] == ["get_current_quote"]


def test_executes_up_to_three_quotes_in_one_round_then_requests_final_response() -> None:
    """一个 Tool Round 可以执行最多三个 Quote，并只进行一次 Final Completion。"""

    agent, _, market_data, llm = make_agent(
        [
            tool_message(("call-1", "GOOG"), ("call-2", "MSFT"), ("call-3", "NVDA")),
            final_message("三只股票的条件式比较"),
        ],
        market_results={
            "GOOG": quote("GOOG", "210"),
            "MSFT": quote("MSFT", "500"),
            "NVDA": quote("NVDA", "180"),
        },
    )

    result = assert_answer(agent.answer(USER_ID, "比较 GOOG、MSFT 和 NVDA"))

    assert result.status is InvestmentResponseStatus.OK
    assert market_data.requested_tickers == ["GOOG", "MSFT", "NVDA"]
    assert len(llm.completions) == 2
    assert llm.completions[1].tools == ()
    tool_results = [
        message for message in llm.completions[1].messages if message.role is LLMRole.TOOL
    ]
    assert len(tool_results) == 3
    assert [source.ticker for source in result.sources[1:]] == ["GOOG", "MSFT", "NVDA"]


def test_rejects_more_than_three_tool_calls_before_market_execution() -> None:
    """超过小上限时不得消耗任何 Market Provider 调用。"""

    agent, _, market_data, _ = make_agent(
        [
            tool_message(
                ("call-1", "GOOG"),
                ("call-2", "MSFT"),
                ("call-3", "NVDA"),
                ("call-4", "AMZN"),
            )
        ]
    )

    failure = assert_failure(agent.answer(USER_ID, "比较四只股票"))

    assert failure.code is InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED
    assert market_data.requested_tickers == []


@pytest.mark.parametrize(
    "tool_call",
    [
        LLMToolCall("call-1", "get_news", {"ticker": "GOOG"}),
        LLMToolCall("call-1", "get_current_quote", {"symbol": "GOOG"}),
        LLMToolCall("call-1", "get_current_quote", {"ticker": "GOOG", "extra": True}),
        LLMToolCall("call-1", "get_current_quote", {"ticker": " "}),
    ],
)
def test_rejects_unknown_tool_or_invalid_arguments(tool_call: LLMToolCall) -> None:
    """Application 必须校验模型输出，不能把任意调用交给 Tool。"""

    agent, _, market_data, _ = make_agent(
        [LLMResult.success(LLMMessage(LLMRole.ASSISTANT, None, (tool_call,)))]
    )

    failure = assert_failure(agent.answer(USER_ID, "question"))

    assert failure.code is InvestmentFailureCode.INVALID_TOOL_CALL
    assert market_data.requested_tickers == []


@pytest.mark.parametrize(
    "market_status",
    [
        MarketDataStatus.NO_DATA,
        MarketDataStatus.AUTHENTICATION_FAILED,
        MarketDataStatus.RATE_LIMITED,
        MarketDataStatus.PROVIDER_UNAVAILABLE,
        MarketDataStatus.INVALID_PROVIDER_RESPONSE,
    ],
)
def test_market_data_failure_can_produce_degraded_safe_answer(
    market_status: MarketDataStatus,
) -> None:
    """Market Failure 应作为 UNKNOWN 返回模型，并由代码计算 DEGRADED。"""

    market_failure: MarketDataResult[MarketQuote] = MarketDataResult.failure(
        market_status,
        "固定 Market Failure",
    )
    agent, _, _, llm = make_agent(
        [tool_message(("call-1", "GOOG")), final_message("当前价格不可用")],
        market_results={"GOOG": market_failure},
    )

    result = assert_answer(agent.answer(USER_ID, "GOOG 现在能买吗？"))

    assert result.status is InvestmentResponseStatus.DEGRADED
    assert result.sources[1].status == market_status.value
    tool_content = llm.completions[1].messages[-1].content
    assert tool_content is not None
    assert json.loads(tool_content)["current_market_fact_available"] is False
    assert "UNKNOWN" in tool_content


@pytest.mark.parametrize(
    ("llm_status", "expected_code"),
    [
        (LLMStatus.INVALID_REQUEST, InvestmentFailureCode.LLM_INVALID_REQUEST),
        (
            LLMStatus.AUTHENTICATION_FAILED,
            InvestmentFailureCode.LLM_AUTHENTICATION_FAILED,
        ),
        (LLMStatus.RATE_LIMITED, InvestmentFailureCode.LLM_RATE_LIMITED),
        (
            LLMStatus.PROVIDER_UNAVAILABLE,
            InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
        ),
        (
            LLMStatus.INVALID_PROVIDER_RESPONSE,
            InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
        ),
    ],
)
def test_llm_provider_failure_is_request_failure_without_final_answer(
    llm_status: LLMStatus,
    expected_code: InvestmentFailureCode,
) -> None:
    """LLM Failure 与 Market Failure 不同，不能降级伪造 Final Answer。"""

    agent, _, market_data, _ = make_agent([LLMResult.failure(llm_status, "固定 LLM Failure")])

    failure = assert_failure(agent.answer(USER_ID, "GOOG 现在能买吗？"))

    assert failure.code is expected_code
    assert market_data.requested_tickers == []


def test_llm_failure_after_market_tool_is_still_request_failure() -> None:
    """即使 Market Tool 成功，Final LLM Failure 也无法形成 Answer。"""

    agent, _, market_data, _ = make_agent(
        [
            tool_message(("call-1", "GOOG")),
            LLMResult.failure(LLMStatus.PROVIDER_UNAVAILABLE, "LLM 不可用"),
        ],
        market_results={"GOOG": quote("GOOG", "210")},
    )

    failure = assert_failure(agent.answer(USER_ID, "GOOG 现在能买吗？"))

    assert failure.code is InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE
    assert market_data.requested_tickers == ["GOOG"]


def test_second_tool_round_is_rejected_even_when_model_requests_valid_tool() -> None:
    """Tool Result 返回后再次请求 Tool 必须明确失败且不执行第二轮。"""

    agent, _, market_data, _ = make_agent(
        [
            tool_message(("call-1", "GOOG")),
            tool_message(("call-2", "MSFT")),
        ],
        market_results={"GOOG": quote("GOOG", "210"), "MSFT": quote("MSFT", "500")},
    )

    failure = assert_failure(agent.answer(USER_ID, "比较 GOOG 和 MSFT"))

    assert failure.code is InvestmentFailureCode.TOOL_ROUND_LIMIT_EXCEEDED
    assert market_data.requested_tickers == ["GOOG"]


@pytest.mark.parametrize("invalid_ticker", ["not/a/ticker", " "])
def test_market_validation_failure_from_model_ticker_is_invalid_tool_call(
    invalid_ticker: str,
) -> None:
    """模型产生的非法 Ticker 属于 Tool Contract Failure，不属于 Provider 降级。"""

    if invalid_ticker.isspace():
        call = LLMToolCall("call-1", "get_current_quote", {"ticker": invalid_ticker})
        expected_requests: list[str] = []
    else:
        call = LLMToolCall("call-1", "get_current_quote", {"ticker": invalid_ticker})
        expected_requests = [invalid_ticker]
    agent, _, market_data, _ = make_agent(
        [LLMResult.success(LLMMessage(LLMRole.ASSISTANT, None, (call,)))],
        market_results={
            invalid_ticker.upper(): MarketDataResult.failure(
                MarketDataStatus.INVALID_SYMBOL,
                "ticker 格式无效",
            )
        },
    )

    failure = assert_failure(agent.answer(USER_ID, "question"))

    assert failure.code is InvestmentFailureCode.INVALID_TOOL_CALL
    assert market_data.requested_tickers == expected_requests


def test_invalid_question_fails_before_reading_portfolio_or_llm() -> None:
    """Application 边界应拒绝空问题且不读取用户事实。"""

    agent, portfolio_reader, market_data, llm = make_agent([final_message()])

    failure = assert_failure(agent.answer(USER_ID, "   "))

    assert failure.code is InvestmentFailureCode.INVALID_QUESTION
    assert portfolio_reader.requested_user_ids == []
    assert market_data.requested_tickers == []
    assert llm.completions == []
