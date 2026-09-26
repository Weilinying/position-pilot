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
from position_pilot.domain.news import NewsArticle, NewsResult, NewsStatus, RecentNews
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


class NewsReadyData(FixedFinancialData):
    """提供一篇带真实 URL 的 Fixture 报道。"""

    def get_recent_news(self, query: NewsQuery) -> NewsResult[RecentNews]:
        article = NewsArticle(
            article_id="alpaca-article-1",
            headline="GOOG 报道标题",
            summary="报道摘要",
            author=None,
            url="https://example.com/goog-news",
            source="Example News",
            symbols=("GOOG",),
            created_at=NOW,
            updated_at=NOW,
        )
        return NewsResult.success(RecentNews(query.ticker, (article,), "ALPACA_NEWS", NOW))


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


def test_missing_strategy_does_not_end_conditional_analysis_prompt() -> None:
    """无持久策略时仍要求使用已知事实分析，而不代用户创建策略。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        prompt = request.messages[0].content
        assert prompt is not None
        assert "不得因缺少策略把整个判断退回给用户" in prompt
        assert "按已知 Position Type 区分分析" in prompt
        assert "不得把假设分支说成用户已有仓位或已确认策略" in prompt
        assert "不得代用户创造目标仓位、价格触发条件或持久 Strategy" in prompt
        assert "不把碎股权限或实际可执行股数列为建议前置或关键澄清问题" in prompt
        assert "账户 Cash 是 Ledger 事实，不等于用户本轮 Budget" in prompt
        assert "只有用户明确询问购买股数、实际可执行数量或账户权限时" in prompt
        assert "不证明用户的长期投资判断或 Thesis 正确" in prompt
        assert "分母不含 Cash，不等于全部资产或市值占比" in prompt
        assert "继续买入不能使该口径占比进一步提高" in prompt
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    result = _agent(ScriptedNativeRuntime(run), FixedFinancialData()).answer_with_history(
        USER_ID,
        "我没有既定策略，现在应该继续分析吗？",
        (),
    )

    assert isinstance(result, InvestmentAnswer)


@pytest.mark.parametrize("question", ["GOOG 当前价格是多少？", "我的账户能买 GOOG 碎股吗？"])
def test_quote_binding_executes_application_tool_and_registers_real_source(question: str) -> None:
    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        arguments = {
            "ticker": "GOOG",
            "request_purpose": "INFORMATION_RETRIEVAL",
        }
        observation = binding.executor(arguments)
        payload = observation.data
        assert payload is not None
        contract = payload["response_contract"]
        assert isinstance(contract, dict)
        assert "required_purchase_execution_status" not in contract
        assert contract["unknown_execution_status_blocks_analysis"] is False
        assert contract["purchase_execution_status_reporting"] == (
            "ONLY_WHEN_USER_ASKS_EXECUTABILITY_OR_ACCOUNT_PERMISSIONS"
        )
        assert contract["price_above_cost_proves_investment_thesis"] is False
        assert contract["purchase_execution_conclusion"] == "PROHIBITED"
        assert contract["fractional_permission_required_for_amount_analysis"] is False
        facts = payload["deterministic_derived_facts"]
        assert isinstance(facts, dict)
        assert facts["executable_purchase_quantity"]["status"] == "UNKNOWN"
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

    result = _agent(runtime, data).answer(USER_ID, question)

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"]
    assert [source.type.value for source in result.sources] == [
        "PORTFOLIO_SNAPSHOT",
        "CURRENT_QUOTE",
    ]


def test_conversation_quote_exposes_observed_source_id_for_inline_citation() -> None:
    def run(request: AgentRunRequest) -> AgentRunResult:
        assert request.messages[0].content is not None
        assert "[source:<source_id>]" in request.messages[0].content
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        arguments = {"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"}
        observation = binding.executor(arguments)
        source_id = str(observation.sources[0]["source_id"])
        candidate = json.dumps(
            {
                "answer": f"GOOG 报价已取得。[source:{source_id}]",
                "source_refs": [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
            }
        )
        return _completed(candidate, sources=observation.sources)

    result = _agent(ScriptedNativeRuntime(run), FixedFinancialData()).answer_with_history(
        USER_ID, "GOOG 当前价格是多少？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert result.sources[0].source_id is not None
    assert f"[source:{result.sources[0].source_id}]" in result.answer


def test_conversation_missing_citation_uses_one_repair_without_new_tool() -> None:
    observed_source_id: str | None = None

    def run(request: AgentRunRequest) -> AgentRunResult:
        nonlocal observed_source_id
        if observed_source_id is None:
            binding = next(
                item for item in request.tools if item.definition.name == "get_current_quote"
            )
            observation = binding.executor(
                {"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"}
            )
            observed_source_id = str(observation.sources[0]["source_id"])
            candidate = _candidate({"type": "CURRENT_QUOTE", "ticker": "GOOG"})
            return _completed(candidate, sources=observation.sources)
        assert request.tools == ()
        assert request.messages[-1].content is not None
        assert observed_source_id in request.messages[-1].content
        return _completed(
            json.dumps(
                {
                    "answer": f"修复后的报价说明。[source:{observed_source_id}]",
                    "source_refs": [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
                }
            )
        )

    runtime = ScriptedNativeRuntime(run)
    result = _agent(runtime, FixedFinancialData()).answer_with_history(
        USER_ID, "GOOG 当前价格是多少？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert len(runtime.requests) == 2
    assert observed_source_id is not None
    assert f"[source:{observed_source_id}]" in result.answer


def test_conversation_portfolio_snapshot_is_not_an_inline_citation() -> None:
    """Portfolio 可在 source_refs 声明，但不能伪装成带 UUID 的 inline 来源。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        if request.tools:
            assert request.messages[0].content is not None
            assert "不要给 Portfolio 事实添加 [source:PORTFOLIO_SNAPSHOT]" in (
                request.messages[0].content
            )
            return _completed(
                json.dumps(
                    {
                        "answer": "账户现金为 $300。[source:PORTFOLIO_SNAPSHOT]",
                        "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                    }
                )
            )
        assert request.messages[-1].content is not None
        assert "不要写 [source:PORTFOLIO_SNAPSHOT]" in request.messages[-1].content
        return _completed(
            json.dumps(
                {
                    "answer": "账户现金为 $300。",
                    "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                }
            )
        )

    runtime = ScriptedNativeRuntime(run)
    result = _agent(runtime, FixedFinancialData()).answer_with_history(
        USER_ID, "我还有多少现金？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert len(runtime.requests) == 2
    assert "[source:PORTFOLIO_SNAPSHOT]" not in result.answer
    assert result.sources[0].type.value == "PORTFOLIO_SNAPSHOT"


def test_conversation_news_source_is_bound_to_observed_article_url() -> None:
    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(item for item in request.tools if item.definition.name == "get_recent_news")
        observation = binding.executor({"ticker": "GOOG"})
        source = observation.sources[0]
        candidate = json.dumps(
            {
                "answer": f"来源报道声称有新进展。[source:{source['source_id']}]",
                "source_refs": [{"type": "RECENT_NEWS", "ticker": "GOOG"}],
            }
        )
        return _completed(candidate, sources=observation.sources)

    data = NewsReadyData()
    result = _agent(ScriptedNativeRuntime(run), data).answer_with_history(
        USER_ID, "GOOG 近期有什么报道？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://example.com/goog-news"
    assert result.sources[0].title == "GOOG 报道标题"
    assert result.sources[0].provider_reference == "alpaca-article-1"


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
        assert observation.data is not None
        contract = observation.data["response_contract"]
        assert isinstance(contract, dict)
        assert "required_purchase_execution_status" not in contract
        assert contract["unknown_execution_status_blocks_analysis"] is False
        assert "required_market_context" in observation.data
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
    runtime = ScriptedNativeRuntime(run)
    result = _agent(runtime, data).answer(
        USER_ID,
        "今天应该加仓 GOOG 吗？",
    )

    assert isinstance(result, InvestmentAnswer)
    assert runtime.requests[0].messages[0].content is not None
    assert "required_market_context 已包含必要的 Market Context" in (
        runtime.requests[0].messages[0].content
    )
    assert data.quote_calls == ["GOOG"]
    assert data.market_context_calls == 1
    assert trace_names == [
        "get_current_quote",
        "get_market_context",
    ]


def test_discretionary_quote_reuses_already_observed_market_context() -> None:
    """模型先请求 Market Context 时，Quote 不再记第二次自动 Tool Call。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        market_binding = next(
            item for item in request.tools if item.definition.name == "get_market_context"
        )
        quote_binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        market = market_binding.executor({})
        arguments = {
            "ticker": "GOOG",
            "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
        }
        quote = quote_binding.executor(arguments)
        assert quote.related_calls == ()
        assert quote.data is not None
        required_context = quote.data["required_market_context"]
        assert isinstance(required_context, dict)
        assert required_context["status"] == "NO_DATA"
        return _completed(
            _candidate({"type": "PORTFOLIO_SNAPSHOT"}),
            trace=(
                AgentToolTrace("get_market_context", {}, market.status, None, market.sources),
                AgentToolTrace("get_current_quote", arguments, quote.status, None, quote.sources),
            ),
            sources=(*market.sources, *quote.sources),
        )

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "GOOG 现在值得加仓吗？")

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"]
    assert data.market_context_calls == 1


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
    assert runtime.requests[0].budget.wall_clock_seconds == 60
    assert runtime.requests[1].budget.model_requests == 1
    assert 0 < runtime.requests[1].budget.wall_clock_seconds < 60


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
