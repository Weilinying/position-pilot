"""Native Investment Agent Production Facade 的离线测试。"""

import hashlib
import json
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

import position_pilot.application.native_investment_agent as native_module
from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolTrace,
)
from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.investment_agent import (
    BASE_SYSTEM_PROMPT,
    CONTEXT_TOOLS,
    LEGACY_AMOUNT_ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
)
from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.application.llm import LLMMessage, LLMRole, LLMStatus
from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.application.native_investment_agent import (
    AMOUNT_ANALYSIS_PROMPT,
    NativeInvestmentAgent,
)
from position_pilot.application.news_service import NewsQuery
from position_pilot.application.source_registry import ContextSource, ContextSourceType
from position_pilot.application.tool_catalog import current_financial_tool_descriptors
from position_pilot.domain.market_context import MarketRegime, MarketRegimeContext
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


class MarketReadyData(FixedFinancialData):
    """提供可引用的固定 Market Context，核对同轮 Source 身份。"""

    def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]:
        self.market_context_calls += 1
        return MarketDataResult.success(
            MarketRegimeContext(
                regime=MarketRegime.NORMAL,
                five_session_return_pct=Decimal("0"),
                twenty_session_drawdown_pct=Decimal("0"),
                twenty_session_annualized_volatility_pct=Decimal("0"),
                triggered_rule_ids=(),
                period_start=NOW - timedelta(days=21),
                period_end=NOW,
                observation_count=21,
                source="ALPACA",
                feed="SIP",
                coverage=MarketDataCoverage.CONSOLIDATED,
                currency="USD",
                adjustment="ALL",
                fetched_at=NOW,
            )
        )


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


@pytest.mark.parametrize(
    ("enabled_tool_names", "tool_budget"),
    ((frozenset(), 0), (frozenset({"get_current_quote"}), 2), (None, 7)),
)
def test_native_budget_follows_exposed_tool_quotas(
    enabled_tool_names: frozenset[str] | None,
    tool_budget: int,
) -> None:
    """本轮暴露集合决定工具额度，并始终为 Final 留一次请求。"""

    runtime = ScriptedNativeRuntime(
        lambda request: _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))
    )
    result = _agent(runtime, FixedFinancialData(), enabled_tool_names=enabled_tool_names).answer(
        USER_ID, "我还有多少现金？"
    )

    assert isinstance(result, InvestmentAnswer)
    assert runtime.requests[0].budget.tool_calls == tool_budget
    assert runtime.requests[0].budget.model_requests == tool_budget + 1


def test_native_budget_changes_with_descriptor_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """修改单个 Tool 的配额后，请求预算无需单独改数字。"""

    descriptors = current_financial_tool_descriptors(CONTEXT_TOOLS)
    revised = (replace(descriptors[0], max_calls_per_run=3), *descriptors[1:])
    monkeypatch.setattr(native_module, "current_financial_tool_descriptors", lambda _: revised)
    runtime = ScriptedNativeRuntime(
        lambda request: _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))
    )

    result = _agent(runtime, FixedFinancialData()).answer(USER_ID, "我还有多少现金？")

    assert isinstance(result, InvestmentAnswer)
    assert runtime.requests[0].budget.tool_calls == 8
    assert runtime.requests[0].budget.model_requests == 9


def test_missing_strategy_does_not_end_conditional_analysis_prompt() -> None:
    """无持久策略时仍要求使用已知事实分析，而不代用户创建策略。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        prompt = request.messages[0].content
        assert prompt is not None
        assert "不得因缺少策略把整个判断退回给用户" in prompt
        assert "按已知 Position Type 区分分析" in prompt
        assert "不得把假设分支说成用户已有仓位或已确认策略" in prompt
        assert "不得代用户创造目标仓位、价格触发条件或持久 Strategy" in prompt
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


@pytest.mark.parametrize("with_history", [False, True])
def test_native_amount_policy_replaces_legacy_policy(with_history: bool) -> None:
    """验证两个入口实际发送唯一金额规则；模型遵循情况仍须在线评测。"""

    runtime = ScriptedNativeRuntime(
        lambda request: _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))
    )
    agent = _agent(runtime, FixedFinancialData())
    if with_history:
        result = agent.answer_with_history(USER_ID, "GOOG 现在值得加仓吗？", ())
    else:
        result = agent.answer(USER_ID, "GOOG 现在值得加仓吗？")

    assert isinstance(result, InvestmentAnswer)
    prompt = runtime.requests[0].messages[0].content
    assert prompt is not None
    assert prompt.startswith(BASE_SYSTEM_PROMPT + "\n")
    assert prompt.count(AMOUNT_ANALYSIS_PROMPT) == 1
    assert "今天或现在已到某个具体价位时，必须调用 get_current_quote" in prompt
    assert "可与 get_recent_news 同轮调用" in prompt
    assert "不证明盘中是否曾触及该价" in prompt
    assert LEGACY_AMOUNT_ANALYSIS_PROMPT not in prompt
    assert "普通加仓分析涉及资金分配时" not in prompt


def test_legacy_system_prompt_remains_frozen() -> None:
    """保留修改前完整 Prompt 的摘要，避免重组改变旧 Runtime 对照基线。"""

    assert hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest() == (
        "8426116a285ec144ac1bebc948683ced4a1bc15de4990748f78835f2b95214b0"
    )


def test_conversation_revision_prompt_requires_fresh_relevant_evidence() -> None:
    """检查跨轮时效 Prompt Contract；真实 Tool 选择另由在线 Eval 验证。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        prompt = request.messages[0].content
        assert prompt is not None
        assert "历史 Assistant Answer 只用于理解指代与当时判断" in prompt
        assert "不能替代本轮 Portfolio Snapshot、当前 confirmed Strategy 或市场事实" in prompt
        assert "用户历史预算和意图更正只按未被后续消息覆盖的适用上下文使用" in prompt
        assert "必须重新调用支撑该结论所需的" in prompt
        assert "不得仅凭历史报价或旧回答断言结论未变" in prompt
        assert request.messages[1] == LLMMessage(LLMRole.USER, "先分析 GOOG。")
        assert request.messages[2] == LLMMessage(LLMRole.ASSISTANT, "此前依据报价给出过分析。")
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    history = (
        LLMMessage(LLMRole.USER, "先分析 GOOG。"),
        LLMMessage(LLMRole.ASSISTANT, "此前依据报价给出过分析。"),
    )
    result = _agent(ScriptedNativeRuntime(run), FixedFinancialData()).answer_with_history(
        USER_ID, "之前的 GOOG 结论现在还成立吗？", history
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
        assert "executable_purchase_quantity" not in facts
        assert "cash_vs_one_share_price" in facts
        assert "price_vs_average_cost_by_position" in facts
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


def test_unsuccessful_tool_source_has_no_citable_id() -> None:
    """失败和空结果保留状态供审计，但不能向模型提供可引用的 Source ID。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        assert request.messages[0].content is not None
        assert "sources 只列本轮成功且可引用的" in request.messages[0].content
        assert "attempt_observations 记录调用状态和失败或空结果" in request.messages[0].content
        assert "source_refs 必须是空数组 []" in request.messages[0].content
        binding = next(item for item in request.tools if item.definition.name == "get_recent_news")
        observation = binding.executor({"ticker": "GOOG"})
        assert observation.status == "NO_NEWS_FOUND"
        assert len(observation.sources) == 1
        assert observation.sources[0]["status"] == "NO_NEWS_FOUND"
        assert observation.sources[0]["source_id"] is None
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    result = _agent(ScriptedNativeRuntime(run), FixedFinancialData()).answer_with_history(
        USER_ID, "GOOG 有近期新闻吗？", ()
    )
    assert isinstance(result, InvestmentAnswer)


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
        facts = observation.data["deterministic_derived_facts"]
        assert isinstance(facts, dict)
        assert "executable_purchase_quantity" not in facts
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
        assert request.messages[0].content is not None
        assert "整体 status 为 DEGRADED" in request.messages[0].content
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
        assert quote.status == "DEGRADED"
        assert quote.sources[0]["status"] == "OK"
        assert market.sources[0]["status"] == "NO_DATA"
        assert quote.data is not None
        required_context = quote.data["required_market_context"]
        assert isinstance(required_context, dict)
        assert required_context["status"] == "NO_DATA"
        source_id = quote.sources[0]["source_id"]
        candidate = json.dumps(
            {
                "answer": f"GOOG 当前报价已取得。[source:{source_id}]",
                "source_refs": [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
            }
        )
        return _completed(
            candidate,
            trace=(
                AgentToolTrace("get_market_context", {}, market.status, None, market.sources),
                AgentToolTrace("get_current_quote", arguments, quote.status, None, quote.sources),
            ),
            sources=(*market.sources, *quote.sources),
        )

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer_with_history(
        USER_ID, "GOOG 现在值得加仓吗？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"]
    assert data.market_context_calls == 1


@pytest.mark.parametrize("market_available", (True, False))
@pytest.mark.parametrize("quote_first", (True, False))
def test_market_context_reuse_keeps_fetch_budget_and_source_identity(
    market_available: bool,
    quote_first: bool,
) -> None:
    """自动与显式 Market 共用同轮 Observation，不重复执行或占 quota。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        bindings = {item.definition.name: item.executor for item in request.tools}
        quote_arguments = {
            "ticker": "GOOG",
            "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
        }
        if quote_first:
            quote = bindings["get_current_quote"](quote_arguments)
            market = bindings["get_market_context"]({})
            assert quote.related_calls[0].provider_fetch_count == 1
            assert market.provider_fetch_count == 0
            assert quote.related_calls[0].sources == market.sources
        else:
            market = bindings["get_market_context"]({})
            quote = bindings["get_current_quote"](quote_arguments)
            assert market.provider_fetch_count == 1
            assert quote.related_calls == ()
            assert quote.data is not None
            assert quote.data["required_market_context"] is not None
        assert market.status == ("OK" if market_available else "NO_DATA")
        if market_available:
            assert market.sources[0]["source_id"] is not None
        else:
            assert market.sources[0]["source_id"] is None
        assert bindings["get_recent_price_history"]({"ticker": "GOOG"}).provider_fetch_count == 1
        assert bindings["get_recent_news"]({"ticker": "GOOG"}).provider_fetch_count == 1
        repeated = bindings["get_market_context"]({})
        assert repeated.cache_reused and repeated.application_execution_count == 0
        assert repeated.sources == market.sources
        assert repeated.provider_fetch_count == 0
        second_quote = bindings["get_current_quote"](
            {"ticker": "AAPL", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"}
        )
        assert second_quote.related_calls == ()
        denied = bindings["get_current_quote"](
            {"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"}
        )
        assert denied.status == "TOOL_QUOTA_EXHAUSTED"
        assert denied.provider_fetch_count == denied.application_execution_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = MarketReadyData() if market_available else FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "分析 GOOG 当前风险。")

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG", "AAPL"]
    assert data.market_context_calls == 1


@pytest.mark.parametrize(
    "tool_name",
    ("get_current_quote", "get_recent_news", "get_recent_price_history"),
)
def test_ticker_tools_replay_without_consuming_new_execution_quota(
    tool_name: str,
) -> None:
    """重复 Observation 不扣新执行额度，但不同参数仍受原有两次额度限制。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(item for item in request.tools if item.definition.name == tool_name)
        arguments = {"ticker": "GOOG"}
        if tool_name == "get_current_quote":
            arguments["request_purpose"] = "INFORMATION_RETRIEVAL"
        first = binding.executor(arguments)
        for _ in range(2):
            cached = binding.executor(arguments)
            assert cached.cache_reused
            assert cached.provider_fetch_count == cached.application_execution_count == 0
            assert cached.data == first.data and cached.sources == first.sources
        assert binding.executor({**arguments, "ticker": "AAPL"}).provider_fetch_count == 1
        denied = binding.executor({**arguments, "ticker": "MSFT"})
        assert denied.status == "TOOL_QUOTA_EXHAUSTED"
        assert denied.provider_fetch_count == denied.application_execution_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    result = _agent(ScriptedNativeRuntime(run), FixedFinancialData()).answer(USER_ID, "分析 GOOG。")

    assert isinstance(result, InvestmentAnswer)


def test_parallel_discretionary_quotes_share_one_market_context_quota() -> None:
    """同轮并发 Tool 必须顺序更新额度与 Market 缓存，不重复预留。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        quote = next(
            item.executor for item in request.tools if item.definition.name == "get_current_quote"
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(
                pool.map(
                    quote,
                    (
                        {"ticker": "GOOG", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"},
                        {"ticker": "AAPL", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"},
                    ),
                )
            )
        assert sum(len(item.related_calls) for item in results) == 1
        denied = quote({"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"})
        assert denied.status == "TOOL_QUOTA_EXHAUSTED"
        assert denied.provider_fetch_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "对比 GOOG 和 AAPL。")

    assert isinstance(result, InvestmentAnswer)
    assert set(data.quote_calls) == {"GOOG", "AAPL"}
    assert data.market_context_calls == 1


def test_reused_market_source_is_declared_once_in_final_answer() -> None:
    """自动取得后显式复用的 Market Source 不应使合法 inline Citation 触发重复错误。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        bindings = {item.definition.name: item.executor for item in request.tools}
        quote = bindings["get_current_quote"](
            {"ticker": "GOOG", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"}
        )
        market = bindings["get_market_context"]({})
        auto_market = quote.related_calls[0]
        assert auto_market.sources == market.sources
        quote_id = quote.sources[0]["source_id"]
        market_id = market.sources[0]["source_id"]
        candidate = json.dumps(
            {
                "answer": (
                    f"GOOG 报价已取得 [source:{quote_id}]，市场状态已取得 [source:{market_id}]。"
                ),
                "source_refs": [
                    {"type": "PORTFOLIO_SNAPSHOT"},
                    {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
                    {"type": "MARKET_CONTEXT", "ticker": "SPY"},
                ],
            }
        )
        return _completed(
            candidate,
            sources=(*quote.sources, *auto_market.sources, *market.sources),
        )

    runtime = ScriptedNativeRuntime(run)
    result = _agent(runtime, MarketReadyData()).answer_with_history(
        USER_ID, "GOOG 现在值得加仓吗？", ()
    )

    assert isinstance(result, InvestmentAnswer)
    assert len(runtime.requests) == 1
    assert [source.type for source in result.sources] == [
        ContextSourceType.PORTFOLIO_SNAPSHOT,
        ContextSourceType.CURRENT_QUOTE,
        ContextSourceType.MARKET_CONTEXT,
    ]


def test_conflicting_source_identity_is_not_deduplicated() -> None:
    """相同 Source ID 的不同内容仍必须由 Citation Validator 拒绝。"""

    source = ContextSource(
        ContextSourceType.MARKET_CONTEXT,
        "OK",
        ticker="SPY",
        feed="SIP",
        source_id=UUID("00000000-0000-0000-0000-000000000123"),
    )
    sources: list[ContextSource] = []
    NativeInvestmentAgent._append_distinct_success_sources(
        sources,
        (source, source, replace(source, feed="CONFLICT")),
    )

    assert len(sources) == 2
    with pytest.raises(CitationValidationError, match="Source ID 重复"):
        validate_citations(f"市场状态 [source:{source.source_id}]。", sources)


def test_invalid_symbol_still_counts_one_real_provider_fetch() -> None:
    """Provider 返回无效标的后，失败 Trace 仍能审计实际请求。"""

    class InvalidQuoteData(FixedFinancialData):
        def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
            self.quote_calls.append(ticker)
            return MarketDataResult.failure(MarketDataStatus.INVALID_SYMBOL, "无效标的")

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        observation = binding.executor(
            {"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"}
        )
        assert observation.status == "INVALID_ARGUMENTS"
        assert observation.provider_fetch_count == 1
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = InvalidQuoteData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "查询 MSFT 报价。")

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["MSFT"]


def test_first_explicit_market_reuse_works_after_four_fetch_slots_are_reserved() -> None:
    """自动取得的 Market Context 即使在第四个获取后显式请求，也不被误拒绝。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        bindings = {item.definition.name: item.executor for item in request.tools}
        quote = bindings["get_current_quote"](
            {"ticker": "GOOG", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"}
        )
        bindings["get_recent_price_history"]({"ticker": "GOOG"})
        bindings["get_recent_news"]({"ticker": "GOOG"})
        market = bindings["get_market_context"]({})
        assert market.status == "NO_DATA"
        assert market.provider_fetch_count == 0
        assert market.sources == quote.related_calls[0].sources
        assert bindings["get_market_context"]({}).cache_reused
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "分析 GOOG。")

    assert isinstance(result, InvestmentAnswer)
    assert data.market_context_calls == 1


def test_provider_exception_keeps_real_fetch_count_and_failure_status() -> None:
    """Provider 抛异常时，模型观察仍标识失败并记录已发出的请求。"""

    class FailingQuoteData(FixedFinancialData):
        def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
            self.quote_calls.append(ticker)
            raise RuntimeError("provider failed")

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            item for item in request.tools if item.definition.name == "get_current_quote"
        )
        observation = binding.executor(
            {"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"}
        )
        assert observation.status == "TOOL_FAILURE"
        assert observation.error_code == "TOOL_FAILURE"
        assert observation.provider_fetch_count == 1
        assert observation.sources == ()
        second = binding.executor({"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"})
        assert second.status == "TOOL_FAILURE" and second.provider_fetch_count == 1
        denied = binding.executor({"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"})
        assert denied.status == "TOOL_QUOTA_EXHAUSTED" and denied.sources == ()
        assert denied.provider_fetch_count == denied.application_execution_count == 0
        assert denied.data is not None
        assert denied.data["existing_observation_available"] is True
        assert denied.data["existing_observation_status"] == "TOOL_FAILURE"
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = FailingQuoteData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "查询 GOOG 报价。")

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG", "GOOG"]


def test_automatic_market_exception_keeps_quote_and_failed_fetch_trace() -> None:
    """复合调用中 Market 抛异常时，Quote 与失败的真实获取分别可审计。"""

    class FailingMarketData(FixedFinancialData):
        def get_current_market_context(self) -> MarketDataResult[MarketRegimeContext]:
            self.market_context_calls += 1
            raise RuntimeError("provider failed")

    def run(request: AgentRunRequest) -> AgentRunResult:
        bindings = {item.definition.name: item.executor for item in request.tools}
        observation = bindings["get_current_quote"](
            {"ticker": "GOOG", "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"}
        )
        assert observation.status == "DEGRADED"
        assert observation.provider_fetch_count == 1
        assert observation.sources[0]["status"] == "OK"
        assert len(observation.related_calls) == 1
        failed_market = observation.related_calls[0]
        assert failed_market.status == "TOOL_FAILURE"
        assert failed_market.error_code == "TOOL_FAILURE"
        assert failed_market.provider_fetch_count == 1
        assert failed_market.sources[0]["status"] == "TOOL_FAILURE"
        assert failed_market.sources[0]["source_id"] is None
        explicit_market = bindings["get_market_context"]({})
        assert explicit_market.status == "TOOL_FAILURE"
        assert explicit_market.error_code == "TOOL_FAILURE"
        assert explicit_market.provider_fetch_count == 0
        assert explicit_market.sources == failed_market.sources
        assert bindings["get_recent_price_history"]({"ticker": "GOOG"}).provider_fetch_count == 1
        assert bindings["get_recent_news"]({"ticker": "GOOG"}).provider_fetch_count == 1
        repeated = bindings["get_market_context"]({})
        assert repeated.cache_reused and repeated.status == "TOOL_FAILURE"
        assert repeated.provider_fetch_count == repeated.application_execution_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = FailingMarketData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "GOOG 可以加仓吗？")

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
        denied = binding.executor(third_arguments)
        assert denied.status == "TOOL_QUOTA_EXHAUSTED"
        assert denied.data == {
            "tool": "get_current_quote",
            "blocking_tool": "get_current_quote",
            "existing_observation_available": False,
            "retry_same_tool": False,
        }
        assert denied.provider_fetch_count == denied.application_execution_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = FixedFinancialData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(
        USER_ID,
        "连续评估 GOOG 加仓机会。",
    )

    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG", "AAPL"]
    assert data.market_context_calls == 1


def test_quote_purpose_change_is_new_execution_and_keeps_required_context() -> None:
    """相同 ticker 不等于相同业务调用，purpose 改变仍应用必要 Context 和 quota。"""

    def run(request: AgentRunRequest) -> AgentRunResult:
        binding = next(
            tool for tool in request.tools if tool.definition.name == "get_current_quote"
        )
        info = {"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"}
        first = binding.executor(info)
        assert first.data is not None and "required_market_context" not in first.data
        cached = binding.executor(info)
        assert cached.cache_reused and cached.sources == first.sources
        risk = binding.executor({**info, "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"})
        assert not risk.cache_reused and risk.application_execution_count == 1
        assert risk.provider_fetch_count == 0
        assert risk.data is not None and risk.data["required_market_context"] is not None
        assert len(risk.related_calls) == 1 and risk.related_calls[0].provider_fetch_count == 1
        replay = binding.executor({**info, "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION"})
        assert replay.cache_reused and replay.related_calls == ()
        assert replay.application_execution_count == replay.provider_fetch_count == 0
        assert risk.related_calls[0].sources[0] in replay.sources
        denied = binding.executor({**info, "ticker": "AAPL"})
        assert denied.status == "TOOL_QUOTA_EXHAUSTED" and denied.provider_fetch_count == 0
        return _completed(_candidate({"type": "PORTFOLIO_SNAPSHOT"}))

    data = MarketReadyData()
    result = _agent(ScriptedNativeRuntime(run), data).answer(USER_ID, "分析 GOOG。")
    assert isinstance(result, InvestmentAnswer)
    assert data.quote_calls == ["GOOG"] and data.market_context_calls == 1


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
    assert runtime.requests[0].budget.model_requests == 8
    assert runtime.requests[0].budget.tool_calls == 7
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
