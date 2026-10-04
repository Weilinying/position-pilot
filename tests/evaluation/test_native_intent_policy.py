"""约束声明与数量请求的离线回归；验证接线和 Trace，不评判真实模型遵循度。"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import pytest
from ask_quality_cases import CASES_BY_ID
from behavioral_harness import USER_ID
from phase4_core_harness import RecordingAgentRuntime, build_native_agent

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolTrace,
)
from position_pilot.application.investment_agent import InvestmentAnswer


@dataclass(frozen=True)
class IntentRegressionCase:
    """独立于 AQ 编号的对照输入；自然语言质量预期留给后续真实模型 Review。"""

    question: str
    request_purpose: str | None
    expected_tools: tuple[str, ...]
    scripted_answer: str
    human_checks: tuple[str, ...]


CASES = (
    IntentRegressionCase(
        "这次最多投入 500 美元",
        None,
        (),
        "已确认，本次投入上限为 500 美元。",
        ("仅确认约束", "不根据已有 GOOG 持仓自行启动投资分析"),
    ),
    IntentRegressionCase(
        "GOOG 这次最多投入 500 美元，现在适合加仓吗？",
        "DISCRETIONARY_CURRENT_RISK_ACTION",
        ("get_current_quote", "get_market_context"),
        "本次预算上限是 500 美元；将结合当前报价和市场环境评估加仓条件。",
        ("保留当前风险动作的必要行情路径", "不主动讨论股数"),
    ),
    IntentRegressionCase(
        "这次最多投入 200 美元",
        None,
        (),
        "已确认，本次投入上限为 200 美元。",
        ("不主动比较预算能否覆盖一股", "不展开投资分析"),
    ),
    IntentRegressionCase(
        "200 美元可以买多少 GOOG？",
        "INFORMATION_RETRIEVAL",
        ("get_current_quote",),
        "当前报价已取得；理论股数需使用 Application 的确定性计算结果，实际订单数量仍未知。",
        ("允许用户要求的数量分析", "不让模型猜测理论股数或实际可执行数量"),
    ),
)


def _assert_expected_trace(
    traces: tuple[AgentToolTrace, ...], expected_tools: tuple[str, ...]
) -> None:
    """检查固定场景的实际 Trace，避免把 Runtime 完成当作路由符合预期。"""

    assert tuple(trace.name for trace in traces) == expected_tools


@pytest.mark.parametrize(
    "case", CASES, ids=("constraint-500", "action", "constraint-200", "quantity")
)
def test_intent_regression_context_and_executor_path(case: IntentRegressionCase) -> None:
    """用脚本模拟预期选择，仅确认 Prompt、完整持仓和既有 Executor 路径能共同工作。"""

    class ScriptedRuntime:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            assert len(request.messages) == 2
            prompt = request.messages[0].content
            assert prompt is not None
            assert "未同时请求分析或行动判断" in prompt
            assert "若同时请求标的、行情、市场分析或买卖判断" in prompt
            assert "用户请求加仓判断且缺少已确认 Strategy" in prompt
            assert "用户请求投资分析但没有适用预算时" in prompt
            assert "不主动将 Budget、Cash、Available Cash 或计划投入金额与单股价格比较" in prompt
            assert "预算可买数量" in prompt
            assert "不声称已写入持久策略" in prompt
            payload = json.loads(request.messages[-1].content or "")
            assert payload["question"] == case.question
            assert payload["portfolio_snapshot"]["positions"][0]["ticker"] == "GOOG"
            assert payload["portfolio_snapshot"]["positions"][0]["position_type"] == "LONG_TERM"
            assert payload["portfolio_snapshot"]["available_cash"] == "4875.77"
            bindings = {binding.definition.name: binding for binding in request.tools}
            assert set(bindings) == {
                "get_current_quote",
                "get_recent_price_history",
                "get_recent_news",
                "get_market_context",
            }
            traces: list[AgentToolTrace] = []
            sources: list[Mapping[str, object]] = []
            if case.request_purpose is not None:
                arguments = {"ticker": "GOOG", "request_purpose": case.request_purpose}
                observation = bindings["get_current_quote"].executor(arguments)
                assert observation.status == "OK"
                traces.append(
                    AgentToolTrace(
                        "get_current_quote",
                        arguments,
                        observation.status,
                        observation.error_code,
                        observation.sources,
                    )
                )
                sources.extend(observation.sources)
                for related in observation.related_calls:
                    traces.append(
                        AgentToolTrace(
                            related.name,
                            related.arguments,
                            related.status,
                            related.error_code,
                            related.sources,
                            invoked_by_model=False,
                        )
                    )
                    sources.extend(related.sources)
            _assert_expected_trace(tuple(traces), case.expected_tools)
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                json.dumps({"answer": case.scripted_answer, "source_refs": []}),
                None,
                tuple(traces),
                tuple(sources),
                None,
                1.0,
            )

    fixture = replace(CASES_BY_ID["AQ03"], executable_questions=(case.question,))
    runtime = RecordingAgentRuntime(ScriptedRuntime())
    result = build_native_agent(fixture, runtime).answer(USER_ID, case.question)

    assert isinstance(result, InvestmentAnswer)
    assert result.answer == case.scripted_answer
    assert case.human_checks
    recorded_trace = cast(list[dict[str, object]], runtime.calls[0]["tool_trace"])
    assert [item["name"] for item in recorded_trace] == list(case.expected_tools)


@pytest.mark.parametrize(
    "tool_name",
    ("get_current_quote", "get_recent_news", "get_recent_price_history", "get_market_context"),
)
def test_constraint_regression_rejects_unexpected_tool_trace(tool_name: str) -> None:
    """离线注入违规 Trace，确认无工具预期会识别过度路由。"""

    with pytest.raises(AssertionError):
        _assert_expected_trace((AgentToolTrace(tool_name, {}, "OK"),), ())


def test_intent_runner_saves_independent_evidence_without_quality_pass(tmp_path: Path) -> None:
    """四组独立请求保存回答及路由差异；脚本完成不会自动通过行为评分。"""

    from test_native_intent_policy_online import run_intent_cases

    class NoToolRuntime:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            assert len(request.messages) == 2
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                '{"answer":"已确认。","source_refs":[]}',
                None,
                (),
                (),
                None,
                1.0,
            )

    artifact_dir = tmp_path / "intent-evidence"
    records = run_intent_cases(NoToolRuntime, artifact_dir)

    assert len(records) == 4
    assert [record["routing_status"] for record in records] == ["PASS", "FAIL", "PASS", "FAIL"]
    assert all(record["behavioral_status"] == "PENDING" for record in records)
    saved = [json.loads(line) for line in (artifact_dir / "cases.jsonl").read_text().splitlines()]
    assert [record["case_id"] for record in saved] == [
        "INTENT01",
        "INTENT02",
        "INTENT03",
        "INTENT04",
    ]
    assert all(record["history_message_count"] == 0 for record in saved)


def test_intent_runner_stops_after_provider_failure(tmp_path: Path) -> None:
    """请求失败保留证据与失败域，不继续消耗下一组调用。"""

    from test_native_intent_policy_online import run_intent_cases

    class FailedRuntime:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "HTTP_ERROR",
                (),
                (),
                None,
                1.0,
                provider_http_status=429,
                provider_error_message="quota exceeded",
            )

    records = run_intent_cases(FailedRuntime, tmp_path / "failed-evidence")

    assert len(records) == 1
    assert records[0]["execution_status"] == "REQUEST_FAILED"
    assert records[0]["failure_domain"] == "RATE_LIMIT"
    assert records[0]["behavioral_status"] == "NOT_EVALUATED"
    assert records[0]["routing_status"] == "NOT_EVALUATED"
