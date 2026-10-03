"""验证 Gemini Core 的一次连接重试，不调用外部模型或改变 Agent 执行策略。"""

import asyncio
import json
from collections.abc import Mapping
from ssl import SSLCertVerificationError

import httpx
import pytest
from phase4_core_harness import RecordingAgentRuntime
from phase4_provider_support import GeminiEvalRuntime, _GeminiRequestTraceModel
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunStatus,
    AgentToolBinding,
)
from position_pilot.application.llm import LLMMessage, LLMResponseFormat, LLMRole, LLMToolDefinition
from position_pilot.application.tool_catalog import ToolExecutionResult


def _final() -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps({"answer": "固定回答。", "source_refs": []}))])


def test_connect_error_retries_same_request_once_and_preserves_first_error() -> None:
    """首次连接失败保留错误记录，重发原请求，不保存异常正文或用户内容。"""
    inputs: list[object] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        inputs.append(messages)
        if len(inputs) == 1:
            raise httpx.ConnectError(
                "https://secret.example?key=DO_NOT_RECORD",
                request=httpx.Request(
                    "POST",
                    "https://secret.example?key=DO_NOT_RECORD",
                    headers={"Authorization": "Bearer DO_NOT_RECORD"},
                ),
            )
        return _final()

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True)
    messages: list[ModelMessage] = [ModelRequest(parts=[])]
    result = asyncio.run(model.request(messages, None, ModelRequestParameters()))
    assert result.parts == _final().parts
    assert len(inputs) == 2 and inputs[0] is inputs[1] is messages
    assert [row["status"] for row in trace] == ["ERROR", "COMPLETED"]
    assert [row["attempt_index"] for row in trace] == [1, 2]
    assert [row["model_request_index"] for row in trace] == [1, 1]
    assert trace[0]["retry_scheduled"] is True
    assert trace[1]["transport_retry"] is True
    assert "DO_NOT_RECORD" not in json.dumps(trace) and "secret.example" not in json.dumps(trace)
    assert "Authorization" not in json.dumps(trace)


def test_two_connect_errors_stop_without_unbounded_retry() -> None:
    """再次连接失败直接返回原异常，最多两个 Provider attempts。"""
    errors = [httpx.ConnectError("first"), httpx.ConnectError("second")]
    calls: list[int] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        raise errors[len(calls) - 1]

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True)
    with pytest.raises(httpx.ConnectError) as caught:
        asyncio.run(model.request([], None, ModelRequestParameters()))
    assert caught.value is errors[1]
    assert len(calls) == 2 and len(trace) == 2
    assert [row["retry_scheduled"] for row in trace] == [True, False]


@pytest.mark.parametrize(
    "error",
    (
        httpx.ConnectTimeout("connect deadline"),
        httpx.ReadTimeout("read deadline"),
        httpx.ReadError("read failed"),
        ModelHTTPError(401, "gemini-3.8-flash"),
        ModelHTTPError(403, "gemini-3.8-flash"),
        ModelHTTPError(429, "gemini-3.8-flash"),
        ModelHTTPError(503, "gemini-3.8-flash"),
        UnexpectedModelBehavior("invalid schema"),
        UsageLimitExceeded("quota exhausted"),
        asyncio.CancelledError(),
    ),
)
def test_non_connection_errors_are_not_retried(error: BaseException) -> None:
    """不把超时、鉴权、限流、输出错误或预算错误转换成连接重试。"""
    calls: list[int] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        raise error

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True)
    with pytest.raises(type(error)) as caught:
        asyncio.run(model.request([], None, ModelRequestParameters()))
    assert caught.value is error
    assert len(calls) == 1 and trace[0]["retry_scheduled"] is False


def test_known_certificate_failure_is_not_retried() -> None:
    """已有 cause chain 明确证书校验失败时不靠重试掩盖配置问题。"""
    error = httpx.ConnectError("connection failed")
    error.__cause__ = SSLCertVerificationError("certificate failed")

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise error

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(model.request([], None, ModelRequestParameters()))
    assert len(trace) == 1 and trace[0]["transport_error_category"] == "TLS_CERTIFICATE"
    assert trace[0]["retry_scheduled"] is False


def test_default_trace_wrapper_retains_no_retry_semantics() -> None:
    """未显式开启的实验入口仍维持原零重试，避免改变 Smoke 定义。"""

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise httpx.ConnectError("failed")

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(model.request([], None, ModelRequestParameters()))
    assert len(trace) == 1 and trace[0]["retry_scheduled"] is False


def test_final_request_connection_retry_does_not_repeat_tool_or_add_model_step() -> None:
    """重试 Final 请求复用相同 Tool Result/Native Schema，模型 step 与物理 attempts 分开。"""
    inputs: list[list[ModelMessage]] = []
    schemas: list[str] = []
    executions: list[str] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        inputs.append(messages)
        output = info.model_request_parameters.output_object
        assert output is not None
        schemas.append(json.dumps(output.json_schema, sort_keys=True))
        if len(inputs) == 1:
            return ModelResponse(parts=[ToolCallPart("get_quote", {"ticker": "GOOG"}, "q1")])
        if len(inputs) == 2:
            raise httpx.ConnectError("connection failed")
        assert info.function_tools == []
        return _final()

    def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
        executions.append(str(arguments["ticker"]))
        return ToolExecutionResult("OK", {"price": "210.25"})

    trace: list[dict[str, object]] = []
    runtime = GeminiEvalRuntime(
        _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True),
        output_mechanism="NATIVE",
    )
    runtime.phase4_request_trace = trace
    recording = RecordingAgentRuntime(runtime)
    result = recording.run(
        AgentRunRequest(
            (LLMMessage(LLMRole.USER, "固定问题。"),),
            (
                AgentToolBinding(
                    LLMToolDefinition(
                        "get_quote",
                        "固定报价",
                        {"type": "object", "properties": {"ticker": {"type": "string"}}},
                    ),
                    execute,
                ),
            ),
            AgentRunBudget(2, 1, 30),
            LLMResponseFormat.JSON_OBJECT,
        )
    )
    assert result.status is AgentRunStatus.COMPLETED
    assert result.model_request_count == 2 and result.tool_attempt_count == 1
    assert executions == ["GOOG"] and inputs[1] is inputs[2]
    assert len(set(schemas)) == 1
    assert [row["model_request_index"] for row in trace] == [1, 2, 2]
    assert [row["attempt_index"] for row in trace] == [1, 1, 2]
    assert trace[1]["tool_results_in_latest_request"] == ["get_quote"]
    assert trace[2]["tool_results_in_latest_request"] == ["get_quote"]
    record = recording.calls[0]
    assert record["provider_model_request_attempt_count"] == 3
    assert record["transport_retry_count"] == record["transport_retry_recovered_count"] == 1
    assert record["model_request_count"] == 2


def test_retry_remains_inside_existing_wall_clock() -> None:
    """重试中的等待仍被原 Run wall-clock 取消，不为第二次尝试重新计时。"""
    calls: list[int] = []

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("connection failed")
        await asyncio.sleep(1)
        return _final()

    trace: list[dict[str, object]] = []
    runtime = GeminiEvalRuntime(
        _GeminiRequestTraceModel(FunctionModel(reply), trace, retry_connect_errors=True),
        output_mechanism="NATIVE",
    )
    result = runtime.run(
        AgentRunRequest(
            (LLMMessage(LLMRole.USER, "固定问题。"),),
            (),
            AgentRunBudget(1, 0, 0.02),
            LLMResponseFormat.JSON_OBJECT,
        )
    )
    assert result.status is AgentRunStatus.BUDGET_EXHAUSTED
    assert result.failure_code == "WALL_CLOCK_BUDGET_EXCEEDED"
    assert result.model_request_count == 1 and len(calls) == 2
    assert [row["error_type"] for row in trace] == ["ConnectError", "CancelledError"]
    assert trace[-1]["retry_scheduled"] is False
