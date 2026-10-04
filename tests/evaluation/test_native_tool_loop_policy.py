"""用真实 Application、FunctionModel 和固定金融 Fixture 验证工具执行语义。"""

import json
from collections.abc import Mapping

import pytest
from ask_quality_cases import CASES_BY_ID
from behavioral_harness import USER_ID
from phase4_core_harness import RecordingAgentRuntime, build_native_agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.investment_agent import InvestmentAnswer
from position_pilot.application.llm import LLMMessage, LLMRole
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


def _final() -> ModelResponse:
    return ModelResponse(
        parts=[
            TextPart(
                json.dumps(
                    {
                        "answer": "基于当前可见资料回答；缺失信息保持 UNKNOWN。",
                        "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                    }
                )
            )
        ]
    )


@pytest.mark.parametrize(
    "tool_name,arguments",
    (
        ("get_current_quote", {"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"}),
        ("get_market_context", {}),
    ),
)
def test_same_observation_loop_stops_at_attempt_budget_with_final(
    tool_name: str, arguments: Mapping[str, object]
) -> None:
    """同参数缓存重放不消耗新执行额度，但至多七次 attempt，仍保留一次 Final。"""
    requests: list[list[str]] = []
    schemas: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append([tool.name for tool in info.function_tools])
        schema = info.model_request_parameters.output_object
        assert schema is not None
        schemas.append(json.dumps(schema.json_schema, sort_keys=True))
        if len(requests) <= 7:
            return ModelResponse(
                parts=[ToolCallPart(tool_name, dict(arguments), f"c{len(requests)}")]
            )
        assert info.function_tools == []
        return _final()

    runtime = RecordingAgentRuntime(
        PydanticAIRuntime(FunctionModel(respond), output_mechanism="NATIVE")
    )
    result = build_native_agent(CASES_BY_ID["AQ12"], runtime).answer(
        USER_ID, "查询 MSFT 当前信息。"
    )
    assert isinstance(result, InvestmentAnswer) and len(runtime.calls) == 1
    call = runtime.calls[0]
    assert call["model_request_count"] == 8
    assert call["tool_attempt_count"] == call["tool_attempt_admission_count"] == 7
    assert call["final_only_request_count"] == 1
    assert call["provider_fetch_count"] == call["application_execution_count"] == 1
    assert call["successful_application_execution_count"] == 1
    assert call["cache_reuse_count"] == 6 and call["per_tool_denial_count"] == 0
    traces = call["tool_trace"]
    assert isinstance(traces, list)
    assert all(trace["sources"] == traces[0]["sources"] for trace in traces)
    assert len(set(schemas)) == 1 and requests[-1] == []


def test_quota_denial_loop_does_not_fetch_and_final_is_still_valid() -> None:
    """两个不同 Quote 用满额度后重复新标的，denial 计 attempt 且不产生虚假来源。"""
    requests: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append(1)
        index = len(requests)
        if index > 3:
            latest = next(
                message for message in reversed(messages) if isinstance(message, ModelRequest)
            )
            observations = []
            for part in latest.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name == "get_current_quote":
                    assert isinstance(part.content, str)
                    observations.append(json.loads(part.content))
            assert observations[0]["status"] == "TOOL_QUOTA_EXHAUSTED"
            assert observations[0]["sources"] == []
            assert observations[0]["data"]["retry_same_tool"] is False
        if index <= 7:
            ticker = ("GOOG", "MSFT")[index - 1] if index <= 2 else "AAPL"
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "get_current_quote",
                        {"ticker": ticker, "request_purpose": "INFORMATION_RETRIEVAL"},
                        f"c{index}",
                    )
                ]
            )
        assert info.function_tools == []
        return _final()

    runtime = RecordingAgentRuntime(
        PydanticAIRuntime(FunctionModel(respond), output_mechanism="NATIVE")
    )
    result = build_native_agent(CASES_BY_ID["AQ12"], runtime).answer(USER_ID, "对比当前个股信息。")
    assert isinstance(result, InvestmentAnswer) and len(runtime.calls) == 1
    call = runtime.calls[0]
    assert call["model_request_count"] == 8 and call["tool_attempt_count"] == 7
    assert call["tool_attempt_admission_count"] == 7 and call["final_only_request_count"] == 1
    assert call["provider_fetch_count"] == call["application_execution_count"] == 2
    assert call["per_tool_denial_count"] == 5 and call["cache_reuse_count"] == 0


def test_recorded_sequential_route_replays_quote_market_and_finishes() -> None:
    """六个真实复现调用不再因第二次 Market 中止，所有原 Observation 仍可见。"""
    sequence = [
        ("get_current_quote", {"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"}),
        ("get_recent_price_history", {"ticker": "MSFT"}),
        ("get_recent_news", {"ticker": "MSFT"}),
        ("get_market_context", {}),
    ]
    sequence.extend([sequence[0], sequence[3]])
    requests: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append(1)
        index = len(requests) - 1
        if index == len(sequence):
            names = [
                getattr(part, "tool_name", None) for message in messages for part in message.parts
            ]
            assert "get_market_context" in names and "get_current_quote" in names
            return _final()
        name, arguments = sequence[index]
        return ModelResponse(parts=[ToolCallPart(name, arguments, f"c{index}")])

    runtime = RecordingAgentRuntime(
        PydanticAIRuntime(FunctionModel(respond), output_mechanism="NATIVE")
    )
    agent = build_native_agent(CASES_BY_ID["AQ12"], runtime)
    history = (
        LLMMessage(LLMRole.USER, "先看看 GOOG。"),
        LLMMessage(LLMRole.ASSISTANT, "已基于可见信息作条件式分析。"),
    )
    result = agent.answer_with_history(USER_ID, "再看看 MSFT。", history)
    assert isinstance(result, InvestmentAnswer) and len(runtime.calls) == 1
    call = runtime.calls[0]
    assert call["model_request_count"] == 7 and call["tool_attempt_count"] == 6
    assert call["provider_fetch_count"] == call["application_execution_count"] == 4
    assert call["cache_reuse_count"] == 2 and call["per_tool_denial_count"] == 0


def test_parallel_identical_risk_quotes_share_context_and_source_identity() -> None:
    """同响应重复 Quote 只做一次复合取证，自动 Market 不增加模型请求或 attempt。"""
    requests: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append(1)
        if len(requests) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "get_current_quote",
                        {
                            "ticker": "MSFT",
                            "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
                        },
                        f"c{i}",
                    )
                    for i in range(2)
                ]
            )
        return _final()

    runtime = RecordingAgentRuntime(
        PydanticAIRuntime(FunctionModel(respond), output_mechanism="NATIVE")
    )
    result = build_native_agent(CASES_BY_ID["AQ12"], runtime).answer(
        USER_ID, "评估 MSFT 加仓风险。"
    )
    assert isinstance(result, InvestmentAnswer) and len(runtime.calls) == 1
    call = runtime.calls[0]
    assert call["model_request_count"] == call["tool_attempt_count"] == 2
    assert call["provider_fetch_count"] == call["application_execution_count"] == 2
    assert call["cache_reuse_count"] == 1
    traces = call["tool_trace"]
    assert isinstance(traces, list)
    assert sum(not trace["invoked_by_model"] for trace in traces) == 1
    reused = next(trace for trace in traces if trace["cache_reused"])
    assert reused["provider_fetch_count"] == reused["application_execution_count"] == 0
    assert len(reused["sources"]) == 2


def test_per_tool_denial_does_not_disable_other_legal_tool_chain() -> None:
    """Quote 拒绝后仍可取得 News/History，不把单工具 quota 当成全局 Final-only。"""
    sequence = [
        ("get_current_quote", {"ticker": "GOOG", "request_purpose": "INFORMATION_RETRIEVAL"}),
        ("get_current_quote", {"ticker": "MSFT", "request_purpose": "INFORMATION_RETRIEVAL"}),
        ("get_current_quote", {"ticker": "AAPL", "request_purpose": "INFORMATION_RETRIEVAL"}),
        ("get_recent_news", {"ticker": "MSFT"}),
        ("get_recent_price_history", {"ticker": "MSFT"}),
    ]
    requests: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append(1)
        index = len(requests) - 1
        if index == len(sequence):
            return _final()
        name, arguments = sequence[index]
        assert name in {tool.name for tool in info.function_tools}
        return ModelResponse(parts=[ToolCallPart(name, arguments, f"c{index}")])

    runtime = RecordingAgentRuntime(
        PydanticAIRuntime(FunctionModel(respond), output_mechanism="NATIVE")
    )
    result = build_native_agent(CASES_BY_ID["AQ12"], runtime).answer(USER_ID, "对比当前市场信息。")
    assert isinstance(result, InvestmentAnswer) and len(runtime.calls) == 1
    call = runtime.calls[0]
    assert call["model_request_count"] == 6 and call["tool_attempt_count"] == 5
    assert call["provider_fetch_count"] == call["application_execution_count"] == 4
    assert call["per_tool_denial_count"] == 1 and call["final_only_request_count"] == 0
