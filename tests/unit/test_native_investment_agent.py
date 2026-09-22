"""Native Investment Agent Production Facade 的离线测试。"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolBudgetExceeded,
    AgentToolTrace,
)
from position_pilot.application.investment_agent import (
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
)
from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.application.llm import LLMStatus
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.news_service import NewsQuery
from position_pilot.domain.market_context import MarketRegimeContext
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.news import NewsResult, NewsStatus, RecentNews
from position_pilot.domain.portfolio import CashBalance, PortfolioState

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class FixedPortfolioReader:
    """返回固定空仓 Portfolio Context。"""

    def get_investment_context(self, user_id: UUID) -> InvestmentPortfolioContext:
        assert user_id == USER_ID
        state = PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(USER_ID, Decimal("1000"), Decimal("300")),
            positions=(),
            transaction_count=0,
        )
        return InvestmentPortfolioContext.from_ledger(state, ())


@dataclass(slots=True)
class FixedFinancialData:
    """只提供 GOOG Quote，并记录 Provider 调用。"""

    quote_calls: list[str] = field(default_factory=list)
    market_context_calls: int = 0

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        self.quote_calls.append(ticker)
        return MarketDataResult.success(
            MarketQuote(
                ticker=ticker,
                last_price=Decimal("210"),
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

    def get_historical_bars(
        self,
        query: HistoricalBarsQuery,
    ) -> MarketDataResult[HistoricalBars]:
        del query
        return MarketDataResult.failure(MarketDataStatus.NO_DATA, "无历史行情")

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        del query
        return NewsResult.failure(NewsStatus.NO_NEWS_FOUND, "无新闻")

    def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]:
        self.market_context_calls += 1
        return MarketDataResult.failure(MarketDataStatus.NO_DATA, "无市场状态")


@dataclass(slots=True)
class ScriptedNativeRuntime:
    """按回调执行高层 Runtime Request。"""

    handler: Callable[[AgentRunRequest], AgentRunResult]
    requests: list[AgentRunRequest] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return self.handler(request)


def _candidate(*refs: Mapping[str, str]) -> str:
    return json.dumps({"answer": "测试回答", "source_refs": list(refs)})


def _completed(
    candidate: str,
    *,
    trace: tuple[AgentToolTrace, ...] = (),
    sources: tuple[Mapping[str, object], ...] = (),
) -> AgentRunResult:
    return AgentRunResult(
        AgentRunStatus.COMPLETED,
        candidate,
        None,
        trace,
        sources,
        None,
        1.0,
    )


def _agent(
    runtime: ScriptedNativeRuntime,
    data: FixedFinancialData,
    *,
    enabled_tool_names: frozenset[str] | None = None,
) -> NativeInvestmentAgent:
    return NativeInvestmentAgent(
        FixedPortfolioReader(),
        data,
        runtime,
        news=data,
        market_context=data,
        clock=lambda: NOW,
        enabled_tool_names=enabled_tool_names,
    )


def test_no_tool_run_preserves_existing_answer_contract() -> None:
    runtime = ScriptedNativeRuntime(
        lambda request: _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))
    )
    data = FixedFinancialData()

    result = _agent(runtime, data).answer(USER_ID, "我目前有持仓吗？")

    assert isinstance(result, InvestmentAnswer)
    assert result.answer == "测试回答"
    assert len(runtime.requests[0].tools) == 4
    assert data.quote_calls == []


def test_quote_binding_executes_application_tool_and_registers_real_source() -> None:
    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        arguments = {
            "ticker": "GOOG",
            "request_purpose": "INFORMATION_RETRIEVAL",
        }
        observation = binding.executor(arguments)
        trace = AgentToolTrace(
            "get_current_quote",
            arguments,
            observation.status,
            observation.error_code,
            observation.sources,
        )
        return _completed(
            _candidate(
                {"type": "PORTFOLIO_SNAPSHOT"},
                {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
            ),
            trace=(trace,),
            sources=observation.sources,
        )

    runtime = ScriptedNativeRuntime(run)
    data = FixedFinancialData()

    result = _agent(runtime, data).answer(USER_ID, "GOOG 当前价格是多少？")

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"]
    assert [source.type.value for source in result.sources] == [
        "PORTFOLIO_SNAPSHOT",
        "CURRENT_QUOTE",
    ]


def test_discretionary_quote_automatically_adds_required_market_context() -> None:
    trace_names: list[str] = []

    def run(request: AgentRunRequest) -> AgentRunResult:
        arguments = {
            "ticker": "GOOG",
            "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
        }
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        observation = binding.executor(arguments)
        traces = [
            AgentToolTrace(
                "get_current_quote",
                arguments,
                observation.status,
                observation.error_code,
                observation.sources,
            )
        ]
        traces.extend(
            AgentToolTrace(
                item.name,
                item.arguments,
                item.status,
                item.error_code,
                item.sources,
            )
            for item in observation.related_calls
        )
        trace_names.extend(trace.name for trace in traces)
        sources = [*observation.sources]
        for item in observation.related_calls:
            sources.extend(item.sources)
        return _completed(
            _candidate({"type": "PORTFOLIO_SNAPSHOT"}),
            trace=tuple(traces),
            sources=tuple(sources),
        )

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(
        USER_ID,
        "今天应该加仓 GOOG 吗？",
    )

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"]
    assert data.market_context_calls == 1
    assert trace_names == [
        "get_current_quote",
        "get_market_context",
    ]


def test_discretionary_quote_is_rejected_before_provider_when_context_disabled() -> None:
    """复合调用缺少必要授权时不得先访问 Quote Provider。"""

    observations = []

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        observation = binding.executor(
            {
                "ticker": "GOOG",
                "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
            }
        )
        observations.append(observation)
        return _completed(
            _candidate({"type": "PORTFOLIO_SNAPSHOT"}),
            trace=(
                AgentToolTrace(
                    "get_current_quote",
                    {
                        "ticker": "GOOG",
                        "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
                    },
                    observation.status,
                    observation.error_code,
                    observation.sources,
                ),
            ),
        )

    data = FixedFinancialData()
    result = _agent(
        ScriptedNativeRuntime(run),
        data,
        enabled_tool_names=frozenset({"get_current_quote"}),
    ).answer(USER_ID, "今天应该加仓 GOOG 吗？")

    assert isinstance(result, InvestmentRequestFailure)
    assert result.code is InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE
    assert observations[0].status == "REQUIRED_CONTEXT_UNAUTHORIZED"
    assert data.quote_calls == []
    assert data.market_context_calls == 0


def test_composite_quote_reserves_two_calls_and_rejects_over_budget() -> None:
    """Quote 与必要 Market Context 都必须计入同一轮 Tool Budget。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        first_arguments = {
            "ticker": "GOOG",
            "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
        }
        second_arguments = {**first_arguments, "ticker": "AAPL"}
        third_arguments = {**first_arguments, "ticker": "MSFT"}
        binding.executor(first_arguments)
        binding.executor(second_arguments)
        with pytest.raises(AgentToolBudgetExceeded):
            binding.executor(third_arguments)
        return AgentRunResult(
            AgentRunStatus.BUDGET_EXHAUSTED,
            None,
            "TOOL_CALL_BUDGET_EXCEEDED",
            (),
            (),
            None,
            1.0,
        )

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(
        USER_ID,
        "连续评估 GOOG 加仓机会。",
    )

    assert isinstance(result, InvestmentRequestFailure)
    assert result.code is InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED
    assert data.quote_calls == ["GOOG", "AAPL"]
    assert data.market_context_calls == 1


def test_invalid_source_uses_one_no_tool_repair_run() -> None:
    calls = 0

    def run(request: AgentRunRequest) -> AgentRunResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(_candidate({"type": "CURRENT_QUOTE", "ticker": "GOOG"}))
        assert request.tools == ()
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    runtime = ScriptedNativeRuntime(run)

    result = _agent(runtime, FixedFinancialData()).answer(USER_ID, "我有持仓吗？")

    assert isinstance(result, InvestmentAnswer)
    assert len(runtime.requests) == 2
    assert runtime.requests[0].budget.model_requests == 3
    assert runtime.requests[1].budget.model_requests == 1
    assert runtime.requests[1].budget.wall_clock_seconds < 30


def test_runtime_failure_maps_to_existing_public_failure_contract() -> None:
    runtime = ScriptedNativeRuntime(
        lambda request: AgentRunResult(
            AgentRunStatus.FAILED,
            None,
            "MODEL_HTTP_FAILURE",
            (),
            (),
            None,
            1.0,
            llm_status=LLMStatus.PROVIDER_UNAVAILABLE,
        )
    )

    result = _agent(runtime, FixedFinancialData()).answer(USER_ID, "我有持仓吗？")

    assert isinstance(result, InvestmentRequestFailure)
    assert result.code is InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE
