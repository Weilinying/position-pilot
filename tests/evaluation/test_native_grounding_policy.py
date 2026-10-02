"""金融事实与历史复述边界的离线接线回归，不证明真实模型遵循度。"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import pytest
from ask_quality_cases import CASES_BY_ID
from behavioral_harness import USER_ID
from phase4_core_harness import build_native_agent

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolTrace,
)
from position_pilot.application.investment_agent import InvestmentAnswer
from position_pilot.application.llm import LLMMessage, LLMRole


@dataclass
class RecordingRuntime:
    """记录 Application 发出的请求，工具行为完全由测试脚本指定。"""

    reply: Callable[[AgentRunRequest], AgentRunResult]
    requests: list[AgentRunRequest] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return self.reply(request)


def _portfolio_only(request: AgentRunRequest) -> AgentRunResult:
    del request
    return AgentRunResult(
        AgentRunStatus.COMPLETED,
        '{"answer":"当前盈亏和个人风险承受度未知。","source_refs":[{"type":"PORTFOLIO_SNAPSHOT"}]}',
        None,
        (),
        (),
        None,
        0.0,
    )


@pytest.mark.parametrize("with_history", (False, True))
def test_cost_only_context_keeps_positions_without_market_or_risk_inference(
    with_history: bool,
) -> None:
    """确认两种入口都收到通用事实边界，完整账本不因未知行情被移除。"""

    runtime = RecordingRuntime(_portfolio_only)
    agent = build_native_agent(CASES_BY_ID["AQ08"], runtime)
    question = "请分别说明现有仓位及减仓前需确认的条件。"
    result = (
        agent.answer_with_history(USER_ID, question, ())
        if with_history
        else agent.answer(USER_ID, question)
    )

    assert isinstance(result, InvestmentAnswer)
    request = runtime.requests[0]
    prompt = request.messages[0].content or ""
    assert "仅在本轮可靠报价已提供时用于描述当前盈亏" in prompt
    assert "Portfolio 成本和 Position Type 不能证明当前浮盈、浮亏或个人风险承受度" in prompt
    assert "示例条件须明确假设，不能冒充用户当前事实" in prompt
    payload = json.loads(request.messages[-1].content or "")
    positions = payload["portfolio_snapshot"]["positions"]
    assert [(p["position_type"], p["shares"], p["average_cost"]) for p in positions] == [
        ("LONG_TERM", "2", "200"),
        ("SWING", "1", "220"),
        ("UNSPECIFIED", "3", "180"),
    ]
    assert all("current_price" not in p and "unrealized_pnl" not in p for p in positions)
    assert payload["decision_context"]["risk_budget"] == "UNKNOWN"
    assert payload["portfolio_snapshot"]["available_cash"] == "4875.77"
    assert not any(source.source_id for source in result.sources)
    assert len(runtime.requests) == 1


@pytest.mark.parametrize(
    "prior_answer",
    (
        "若长期逻辑未变可继续评估；风险条件未知，尚未给出观望决定。",
        "由于关键入场条件尚未满足，当前建议观望；条件变化时重新评估。",
    ),
    ids=("conditional-undecided", "explicit-wait-with-conditions"),
)
def test_history_keeps_original_decision_strength_and_fresh_evidence_requirement(
    prior_answer: str,
) -> None:
    """既有条件式与明确观望历史均原样提供，不在程序中重写历史结论。"""

    history = (
        LLMMessage(LLMRole.USER, "先分析 GOOG。"),
        LLMMessage(LLMRole.ASSISTANT, prior_answer),
        LLMMessage(LLMRole.USER, "再看看 MSFT。"),
        LLMMessage(LLMRole.ASSISTANT, "MSFT 仍需按自身条件评估。"),
    )
    runtime = RecordingRuntime(_portfolio_only)
    result = build_native_agent(CASES_BY_ID["AQ12"], runtime).answer_with_history(
        USER_ID, "回到 GOOG，刚才的结论需要改吗？", history
    )

    assert isinstance(result, InvestmentAnswer)
    request = runtime.requests[0]
    assert request.messages[1:-1] == history
    prompt = request.messages[0].content or ""
    assert "复述须保留原判断的条件、假设和未决状态" in prompt
    assert "不能强化成先前已作出的买卖或观望决定" in prompt
    assert "必须重新调用支撑该结论所需的" in prompt
    assert "不得仅凭历史报价或旧回答断言结论未变" in prompt
    assert "不能替代本轮 Portfolio Snapshot、当前 confirmed Strategy 或市场事实" in prompt


def test_topic_return_can_get_fresh_quote_and_distinct_current_source() -> None:
    """脚本执行三轮真实 Fixture Executor，确认新规则不阻止取证或串用来源。"""

    tickers = iter(("GOOG", "MSFT", "GOOG"))
    observed_sources: list[Mapping[str, object]] = []
    observed_data: list[Mapping[str, object]] = []

    def reply(request: AgentRunRequest) -> AgentRunResult:
        ticker = next(tickers)
        binding = next(t for t in request.tools if t.definition.name == "get_current_quote")
        arguments = {"ticker": ticker, "request_purpose": "INFORMATION_RETRIEVAL"}
        observation = binding.executor(arguments)
        assert observation.status == "OK"
        assert observation.data is not None
        source = observation.sources[0]
        assert source["ticker"] == ticker and source["source_id"]
        observed_sources.append(source)
        observed_data.append(observation.data)
        answer = (
            f"已取得本轮 {ticker} 报价 [source:{source['source_id']}]。"
            "继续按原来的条件与未决状态比较，不把它改写成既有行动决定。"
        )
        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            json.dumps(
                {
                    "answer": answer,
                    "source_refs": [{"type": "CURRENT_QUOTE", "ticker": ticker}],
                }
            ),
            None,
            (AgentToolTrace(binding.definition.name, arguments, "OK", None, observation.sources),),
            observation.sources,
            None,
            0.0,
        )

    runtime = RecordingRuntime(reply)
    agent = build_native_agent(CASES_BY_ID["AQ12"], runtime)
    history: tuple[LLMMessage, ...] = ()
    questions = ("先分析 GOOG。", "再看看 MSFT。", "回到 GOOG，刚才的结论需要改吗？")
    for question in questions:
        result = agent.answer_with_history(USER_ID, question, history)
        assert isinstance(result, InvestmentAnswer)
        history += (
            LLMMessage(LLMRole.USER, question),
            LLMMessage(LLMRole.ASSISTANT, result.answer),
        )

    assert len(runtime.requests) == 3
    assert runtime.requests[2].messages[1:-1] == history[:-2]
    assert len({s["source_id"] for s in observed_sources}) == 3
    assert [s["ticker"] for s in observed_sources] == ["GOOG", "MSFT", "GOOG"]
    assert [data["last_price"] for data in observed_data] == ["210.25", "500.50", "210.25"]
    current_data = json.loads(json.dumps(observed_data[2]))
    assert current_data["current_market_fact_available"] is True
    assert current_data["deterministic_derived_facts"]["price_vs_average_cost_by_position"] == [
        {"ticker": "GOOG", "position_type": "LONG_TERM", "price_vs_average_cost": "ABOVE"}
    ]
    assert "本轮可靠报价已提供时用于描述当前盈亏" in (runtime.requests[2].messages[0].content or "")
