"""PydanticAI Production Adapter 的离线 Native Loop 测试。"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr, ValidationError
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunStatus,
    AgentToolBinding,
    AgentToolBudgetExceeded,
)
from position_pilot.application.investment_answer import parse_structured_answer
from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMRole,
    LLMStatus,
    LLMToolDefinition,
)
from position_pilot.application.source_registry import SourceValidator
from position_pilot.application.tool_catalog import (
    ToolExecutionRecord,
    ToolExecutionResult,
)
from position_pilot.config import Settings
from position_pilot.integrations import pydantic_ai_runtime
from position_pilot.integrations.pydantic_ai_runtime import (
    PydanticAIRuntime,
    create_pydantic_ai_runtime,
)


@dataclass(slots=True)
class ScriptedModel:
    """使用 PydanticAI 官方 FunctionModel 记录原生 Loop 消息。"""

    responses: list[ModelResponse]
    calls: list[list[ModelMessage]] = field(default_factory=list)

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        """返回下一条脚本响应。"""

        del info
        self.calls.append(list(messages))
        return self.responses.pop(0)


def _request(
    *,
    tools: tuple[AgentToolBinding, ...] = (),
    response_format: str = "TEXT",
    budget: AgentRunBudget | None = None,
) -> AgentRunRequest:
    """创建最小 Provider-neutral Run Request。"""

    from position_pilot.application.llm import LLMResponseFormat

    return AgentRunRequest(
        (
            LLMMessage(LLMRole.SYSTEM, "只根据可用事实作答。"),
            LLMMessage(LLMRole.USER, "分析 GOOG。"),
        ),
        tools,
        budget or AgentRunBudget(model_requests=4, tool_calls=4, wall_clock_seconds=30),
        LLMResponseFormat(response_format),
    )


def _runtime(script: ScriptedModel) -> PydanticAIRuntime:
    """创建 Fixture Runtime，不触碰外部配置或网络。"""

    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        """给 FunctionModel 提供具名函数。"""

        return script(messages, info)

    return PydanticAIRuntime(FunctionModel(scripted, model_name="qwen-fixture"))


def _definition(name: str) -> LLMToolDefinition:
    """创建单字符串参数的 Tool Definition。"""

    return LLMToolDefinition(
        name,
        f"调用 {name}",
        {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    )


def _tool_response(name: str, arguments: Mapping[str, object], call_id: str) -> ModelResponse:
    """创建原生 Tool Call Response。"""

    return ModelResponse(
        parts=(ToolCallPart(name, dict(arguments), call_id),),
        usage=RequestUsage(input_tokens=3, output_tokens=2),
    )


def _text_response(text: str) -> ModelResponse:
    """创建带真实 Usage 的最终文本 Response。"""

    return ModelResponse(
        parts=(TextPart(text),),
        usage=RequestUsage(input_tokens=4, output_tokens=2),
    )


def _final_output_response(
    answer: str,
    source_refs: list[dict[str, str]],
) -> ModelResponse:
    """创建由 PydanticAI Final Output Tool 承载的脚本响应。"""

    return ModelResponse(
        parts=(
            ToolCallPart(
                "final_investment_answer",
                {"answer": answer, "source_refs": source_refs},
                "final-1",
            ),
        ),
        usage=RequestUsage(input_tokens=6, output_tokens=4),
    )


def test_json_final_output_tool_returns_provider_neutral_candidate_without_tool_budget() -> None:
    """无金融工具时，Final Output Tool 仍能在零普通 Tool Budget 下完成。"""

    script = ScriptedModel([_final_output_response("没有可用新数据。", [])])

    result = _runtime(script).run(
        _request(response_format="JSON_OBJECT", budget=AgentRunBudget(1, 0, 30))
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert result.final_candidate is not None
    assert parse_structured_answer(result.final_candidate).answer == "没有可用新数据。"
    assert result.tool_trace == ()
    assert result.usage is not None and result.usage.total_tokens == 10
    assert len(script.calls) == 1


def test_json_tool_loop_keeps_application_source_validation_authority() -> None:
    """Output Tool 不占普通 Tool Trace，候选仍交给 Application 校验来源。"""

    binding = AgentToolBinding(
        _definition("get_quote"),
        lambda arguments: ToolExecutionResult(
            "OK",
            {"price": "210.25"},
            sources=(
                {
                    "source_id": "quote-1",
                    "type": "CURRENT_QUOTE",
                    "ticker": "GOOG",
                    "status": "OK",
                },
            ),
        ),
    )
    script = ScriptedModel(
        [
            _tool_response("get_quote", {"ticker": "GOOG"}, "call-1"),
            _final_output_response(
                "报价已核验。",
                [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
            ),
        ]
    )

    result = _runtime(script).run(
        _request(
            tools=(binding,),
            response_format="JSON_OBJECT",
            budget=AgentRunBudget(2, 1, 30),
        )
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert [trace.name for trace in result.tool_trace] == ["get_quote"]
    assert result.final_candidate is not None
    assert parse_structured_answer(result.final_candidate).source_refs[0].ticker == "GOOG"
    assert SourceValidator.evaluate(result.final_candidate, ())[1] is not None
    assert len(script.calls) == 2


def test_invalid_json_output_tool_arguments_are_provider_response_failure() -> None:
    """不启用框架隐式重试；非法输出不冒充 Provider 不可用。"""

    script = ScriptedModel(
        [ModelResponse(parts=(ToolCallPart("final_investment_answer", {"answer": "缺字段"}),))]
    )

    result = _runtime(script).run(_request(response_format="JSON_OBJECT"))

    assert result.status is AgentRunStatus.FAILED
    assert result.failure_code == "INVALID_PROVIDER_RESPONSE"
    assert result.llm_status is LLMStatus.INVALID_PROVIDER_RESPONSE
    assert result.framework_error_kind == "OUTPUT_RETRY_EXHAUSTED"
    assert len(script.calls) == 1


@pytest.mark.parametrize(
    ("message", "expected_kind"),
    (
        ("Invalid response, unable to find output", "OUTPUT_RESPONSE_INVALID"),
        ("Invalid response from fixture endpoint", "PROVIDER_RESPONSE_SHAPE_INVALID"),
    ),
)
def test_framework_diagnostic_excludes_exception_body(message: str, expected_kind: str) -> None:
    """只记录已知失败类别与 Cause 类型，不保留异常正文。"""

    def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        try:
            raise ValueError("private cause")
        except ValueError as cause:
            raise UnexpectedModelBehavior(message, '{"secret":"private body"}') from cause

    result = PydanticAIRuntime(FunctionModel(fail, model_name="qwen-fixture")).run(_request())

    assert result.framework_error_kind == expected_kind
    assert result.framework_error_cause == "ValueError"
    assert "private" not in repr(result)


def test_json_repair_call_accepts_prior_text_candidate_and_zero_tool_budget() -> None:
    """Application 一次无 Tool Repair 仍通过结构化输出工具返回候选。"""

    script = ScriptedModel([_final_output_response("已修正。", [])])
    request = AgentRunRequest(
        (
            LLMMessage(LLMRole.SYSTEM, "只根据可用事实作答。"),
            LLMMessage(LLMRole.USER, "分析 GOOG。"),
            LLMMessage(LLMRole.ASSISTANT, '{"answer": bad json}'),
            LLMMessage(LLMRole.USER, "修正输出格式。"),
        ),
        (),
        AgentRunBudget(1, 0, 30),
        LLMResponseFormat.JSON_OBJECT,
    )

    result = _runtime(script).run(request)

    assert result.status is AgentRunStatus.COMPLETED
    assert result.final_candidate is not None
    assert parse_structured_answer(result.final_candidate).answer == "已修正。"


def test_no_tool_native_loop_returns_final_candidate_and_usage() -> None:
    """No-tool Run 使用 Agent.run_sync，结果包含候选文本和 Usage。"""

    script = ScriptedModel([_text_response("基于当前事实的分析。")])

    result = _runtime(script).run(_request())

    assert result.status is AgentRunStatus.COMPLETED
    assert result.final_candidate == "基于当前事实的分析。"
    assert result.tool_trace == ()
    assert result.llm_status is LLMStatus.OK
    assert result.usage is not None
    assert result.usage.total_tokens > 0
    assert len(script.calls) == 1


def test_one_tool_binds_application_executor_and_returns_sources() -> None:
    """One-tool Loop 将参数交给 Application，并保留 Tool Result 来源。"""

    calls: list[Mapping[str, object]] = []

    def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
        calls.append(arguments)
        return ToolExecutionResult(
            "OK",
            {"price": "210.25"},
            sources=({"source_id": "quote-1", "type": "CURRENT_QUOTE", "status": "OK"},),
        )

    binding = AgentToolBinding(_definition("get_quote"), execute)
    script = ScriptedModel(
        [
            _tool_response("get_quote", {"ticker": "GOOG"}, "call-1"),
            _text_response("报价已核验。"),
        ]
    )

    result = _runtime(script).run(_request(tools=(binding,)))

    assert result.status is AgentRunStatus.COMPLETED
    assert calls == [{"ticker": "GOOG"}]
    assert result.tool_trace[0].name == "get_quote"
    assert result.tool_trace[0].arguments == {"ticker": "GOOG"}
    assert result.tool_trace[0].sources == (
        {"source_id": "quote-1", "type": "CURRENT_QUOTE", "status": "OK"},
    )
    assert result.sources == ({"source_id": "quote-1", "type": "CURRENT_QUOTE", "status": "OK"},)
    assert len(script.calls) == 2
    tool_return = next(
        part
        for message in script.calls[1]
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    )
    observation = json.loads(tool_return.content)
    assert observation["sources"] == [
        {"source_id": "quote-1", "type": "CURRENT_QUOTE", "status": "OK"}
    ]
    assert observation["attempt_observations"] == [
        {"tool_name": "get_quote", "status": "OK", "error_code": None}
    ]


@pytest.mark.parametrize(
    ("status", "error_code"),
    (("NO_NEWS_FOUND", None), ("PROVIDER_UNAVAILABLE", "NEWS_PROVIDER_UNAVAILABLE")),
)
def test_failed_source_is_not_model_citable_but_remains_in_trace(
    status: str,
    error_code: str | None,
) -> None:
    """空结果与 Provider Failure 使用独立 Attempt Observation，不伪装为 Source。"""

    source = {
        "type": "RECENT_NEWS",
        "status": status,
        "ticker": "GOOG",
        "source_id": None,
    }
    binding = AgentToolBinding(
        _definition("get_recent_news"),
        lambda arguments: ToolExecutionResult(
            status,
            error_code=error_code,
            sources=(source,),
        ),
    )
    bridge = pydantic_ai_runtime._ToolBridge(
        {"get_recent_news": binding}, AgentRunBudget(2, 1, 30), lambda: 0.0, 0.0
    )

    observation = json.loads(bridge.execute("get_recent_news", {"ticker": "GOOG"}))

    assert observation["sources"] == []
    assert observation["attempt_observations"] == [
        {"tool_name": "get_recent_news", "status": status, "error_code": error_code}
    ]
    assert observation["status"] == status
    assert bridge.sources == [source]
    assert bridge.tool_trace[0].sources == (source,)


def test_degraded_observation_exposes_only_successful_sources_and_all_attempts() -> None:
    """混合结果保留成功来源与失败状态，内部 Trace 仍保存完整尝试。"""

    quote = {
        "type": "CURRENT_QUOTE",
        "status": "OK",
        "ticker": "GOOG",
        "source_id": "quote-1",
    }
    failed_market = {
        "type": "MARKET_CONTEXT",
        "status": "NO_DATA",
        "ticker": "SPY",
        "source_id": None,
    }
    binding = AgentToolBinding(
        _definition("get_quote"),
        lambda arguments: ToolExecutionResult(
            "DEGRADED",
            {"required_market_context": {"status": "NO_DATA"}},
            sources=(quote,),
            related_calls=(
                ToolExecutionRecord(
                    "get_market_context",
                    {},
                    "NO_DATA",
                    "MARKET_DATA_NO_DATA",
                    (failed_market,),
                ),
            ),
        ),
    )
    bridge = pydantic_ai_runtime._ToolBridge(
        {"get_quote": binding}, AgentRunBudget(2, 2, 30), lambda: 0.0, 0.0
    )

    observation = json.loads(bridge.execute("get_quote", {"ticker": "GOOG"}))

    assert observation["status"] == "DEGRADED"
    assert observation["sources"] == [quote]
    assert observation["attempt_observations"] == [
        {"tool_name": "get_quote", "status": "DEGRADED", "error_code": None},
        {
            "tool_name": "get_market_context",
            "status": "NO_DATA",
            "error_code": "MARKET_DATA_NO_DATA",
        },
    ]
    assert bridge.sources == [quote, failed_market]
    assert [trace.sources for trace in bridge.tool_trace] == [(quote,), (failed_market,)]


def test_model_visible_sources_exclude_malformed_reference_identity() -> None:
    """不把缺少可引用身份的 OK 审计项展示为可声明 Source。"""

    missing_type = {"status": "OK", "source_id": "quote-1"}
    invalid_id = {"type": "CURRENT_QUOTE", "status": "OK", "source_id": 42}
    binding = AgentToolBinding(
        _definition("get_quote"),
        lambda arguments: ToolExecutionResult("OK", sources=(missing_type, invalid_id)),
    )
    bridge = pydantic_ai_runtime._ToolBridge(
        {"get_quote": binding}, AgentRunBudget(2, 1, 30), lambda: 0.0, 0.0
    )

    observation = json.loads(bridge.execute("get_quote", {"ticker": "GOOG"}))

    assert observation["sources"] == []
    assert bridge.sources == [missing_type, invalid_id]
    assert bridge.tool_trace[0].sources == (missing_type, invalid_id)


def test_multi_tool_loop_preserves_order_and_arguments() -> None:
    """Multi-tool Loop 支持 Search → Fetch，并保持调用顺序。"""

    calls: list[str] = []

    def search(arguments: Mapping[str, object]) -> ToolExecutionResult:
        calls.append(f"search:{arguments['ticker']}")
        return ToolExecutionResult("OK", {"url": "https://example.test/source"})

    def fetch(arguments: Mapping[str, object]) -> ToolExecutionResult:
        calls.append(f"fetch:{arguments['ticker']}")
        return ToolExecutionResult("OK", {"content": "source text"})

    bindings = (
        AgentToolBinding(_definition("search"), search),
        AgentToolBinding(_definition("fetch"), fetch),
    )
    script = ScriptedModel(
        [
            _tool_response("search", {"ticker": "GOOG"}, "call-1"),
            _tool_response("fetch", {"ticker": "GOOG"}, "call-2"),
            _text_response("已完成两步读取。"),
        ]
    )

    result = _runtime(script).run(_request(tools=bindings))

    assert result.status is AgentRunStatus.COMPLETED
    assert calls == ["search:GOOG", "fetch:GOOG"]
    assert [trace.name for trace in result.tool_trace] == ["search", "fetch"]


def test_related_application_call_has_separate_trace_source_and_budget_count() -> None:
    """复合 Executor 的自动获取进入 Trace，但不是模型显式调用。"""

    def quote(arguments: Mapping[str, object]) -> ToolExecutionResult:
        del arguments
        return ToolExecutionResult(
            "OK",
            {"price": "210"},
            sources=({"type": "CURRENT_QUOTE"},),
            related_calls=(
                ToolExecutionRecord(
                    "get_market_context",
                    {},
                    "OK",
                    sources=({"type": "MARKET_CONTEXT"},),
                ),
            ),
        )

    script = ScriptedModel(
        [
            _tool_response("get_quote", {"ticker": "GOOG"}, "call-1"),
            _text_response("报价和市场环境已核验。"),
        ]
    )

    result = _runtime(script).run(
        _request(tools=(AgentToolBinding(_definition("get_quote"), quote),))
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert [trace.name for trace in result.tool_trace] == [
        "get_quote",
        "get_market_context",
    ]
    assert result.sources == (
        {"type": "CURRENT_QUOTE"},
        {"type": "MARKET_CONTEXT"},
    )
    assert [item.invoked_by_model for item in result.tool_trace] == [True, False]
    assert [item.provider_fetch_count for item in result.tool_trace] == [1, 1]


def test_auto_market_then_explicit_reuse_keeps_four_model_invocations() -> None:
    """自动 Market 获取不占模型 Invocation，首次显式复用不重复获取。"""

    quote = AgentToolBinding(
        _definition("get_quote"),
        lambda arguments: ToolExecutionResult(
            "OK",
            related_calls=(
                ToolExecutionRecord("get_market_context", {}, "NO_DATA", provider_fetch_count=1),
            ),
        ),
    )
    market = AgentToolBinding(
        _definition("get_market_context"),
        lambda arguments: ToolExecutionResult("NO_DATA", provider_fetch_count=0),
    )
    history = AgentToolBinding(
        _definition("get_history"),
        lambda arguments: ToolExecutionResult("NO_DATA"),
    )
    news = AgentToolBinding(
        _definition("get_news"),
        lambda arguments: ToolExecutionResult("NO_NEWS_FOUND"),
    )
    script = ScriptedModel(
        [
            _tool_response("get_quote", {"ticker": "GOOG"}, "call-1"),
            _tool_response("get_market_context", {"ticker": "GOOG"}, "call-2"),
            _tool_response("get_history", {"ticker": "GOOG"}, "call-3"),
            _tool_response("get_news", {"ticker": "GOOG"}, "call-4"),
            _text_response("已保留失败状态并完成分析。"),
        ]
    )

    result = _runtime(script).run(
        _request(tools=(quote, market, history, news), budget=AgentRunBudget(5, 4, 30))
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert [item.name for item in result.tool_trace] == [
        "get_quote",
        "get_market_context",
        "get_market_context",
        "get_history",
        "get_news",
    ]
    assert sum(item.invoked_by_model for item in result.tool_trace) == 4
    assert sum(item.provider_fetch_count for item in result.tool_trace) == 4
    assert result.tool_trace[2].provider_fetch_count == 0


def test_application_tool_budget_exception_maps_to_stable_runtime_failure() -> None:
    """Application 预留拒绝不得被降级成普通 Tool Failure。"""

    def reject(arguments: Mapping[str, object]) -> ToolExecutionResult:
        del arguments
        raise AgentToolBudgetExceeded

    script = ScriptedModel([_tool_response("get_quote", {"ticker": "GOOG"}, "call-1")])

    result = _runtime(script).run(
        _request(tools=(AgentToolBinding(_definition("get_quote"), reject),))
    )

    assert result.status is AgentRunStatus.BUDGET_EXHAUSTED
    assert result.failure_code == "TOOL_CALL_BUDGET_EXCEEDED"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    (
        (401, LLMStatus.AUTHENTICATION_FAILED),
        (429, LLMStatus.RATE_LIMITED),
        (500, LLMStatus.PROVIDER_UNAVAILABLE),
    ),
)
def test_provider_http_failure_maps_to_stable_status(
    status_code: int,
    expected: LLMStatus,
) -> None:
    """Provider HTTP 异常只暴露稳定的 LLMStatus，不泄露异常正文。"""

    def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise ModelHTTPError(status_code, "fixture", {"secret": "must-not-leak"})

    result = PydanticAIRuntime(FunctionModel(fail, model_name="qwen-fixture")).run(_request())

    assert result.status is AgentRunStatus.FAILED
    assert result.llm_status is expected
    assert result.failure_code == "MODEL_HTTP_FAILURE"
    assert result.provider_http_status == status_code
    assert result.provider_error_code is None
    assert result.provider_error_message is None
    assert "secret" not in repr(result)


def test_provider_invalid_parameter_details_remain_internal() -> None:
    """保留可诊断的错误码与说明，不把完整 Provider 正文传给业务失败响应。"""

    message = (
        "The tool_choice parameter does not support being set to required "
        "or object in thinking mode"
    )

    def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise ModelHTTPError(
            400,
            "fixture",
            {"error": {"code": "InvalidParameter", "message": message}, "secret": "must-not-leak"},
        )

    result = PydanticAIRuntime(FunctionModel(fail, model_name="qwen-fixture")).run(_request())

    assert result.status is AgentRunStatus.FAILED
    assert result.llm_status is LLMStatus.INVALID_REQUEST
    assert result.failure_code == "MODEL_HTTP_FAILURE"
    assert result.provider_http_status == 400
    assert result.provider_error_code == "InvalidParameter"
    assert result.provider_error_message == message
    assert message not in repr(result)
    assert "must-not-leak" not in repr(result)


def test_usage_unknown_is_explicit_and_timeout_retry_boundaries_are_fixed() -> None:
    """缺少 Usage 保持 UNKNOWN，Adapter 不隐式重试且拒绝非法 timeout。"""

    result = PydanticAIRuntime(FunctionModel(lambda messages, info: _text_response("ok")))
    unknown_usage = result._map_usage(RequestUsage())

    assert unknown_usage is None
    assert (
        PydanticAIRuntime(
            FunctionModel(lambda messages, info: _text_response("ok")),
            timeout_seconds=7,
            max_retries=0,
        ).max_retries
        == 0
    )
    with pytest.raises(ValueError):
        PydanticAIRuntime(
            FunctionModel(lambda messages, info: _text_response("ok")),
            timeout_seconds=0,
        )
    with pytest.raises(ValueError):
        PydanticAIRuntime(
            FunctionModel(lambda messages, info: _text_response("ok")),
            max_retries=-1,
        )
    with pytest.raises(ValueError):
        PydanticAIRuntime(
            FunctionModel(lambda messages, info: _text_response("ok")),
            max_retries=1,
        )


def test_tool_failure_is_explicit_observation_not_runtime_exception() -> None:
    """Application Tool Failure 进入 Tool Trace，Runtime 仍由模型生成最终候选。"""

    def fail(arguments: Mapping[str, object]) -> ToolExecutionResult:
        del arguments
        raise RuntimeError("provider secret")

    binding = AgentToolBinding(_definition("get_quote"), fail)
    script = ScriptedModel(
        [
            _tool_response("get_quote", {"ticker": "GOOG"}, "call-1"),
            _text_response("数据不可用，保持 UNKNOWN。"),
        ]
    )

    result = _runtime(script).run(_request(tools=(binding,)))

    assert result.status is AgentRunStatus.COMPLETED
    assert result.tool_trace[0].status == "TOOL_FAILURE"
    assert result.warnings == ("TOOL_FAILURE:get_quote",)


def test_missing_credential_is_stable_authentication_failure() -> None:
    """缺少 Credential 时不在装配阶段泄露 SDK 异常。"""

    result = PydanticAIRuntime(None).run(_request())

    assert result.status is AgentRunStatus.FAILED
    assert result.failure_code == "MODEL_CREDENTIAL_MISSING"
    assert result.llm_status is LLMStatus.AUTHENTICATION_FAILED


def test_wall_clock_budget_interrupts_entire_native_loop() -> None:
    """总 Wall-clock Ceiling 必须中断尚未完成的 Model Request。"""

    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        await asyncio.sleep(0.05)
        return _text_response("不应完成")

    result = PydanticAIRuntime(FunctionModel(slow, model_name="slow-fixture")).run(
        _request(budget=AgentRunBudget(2, 0, 0.01))
    )

    assert result.status is AgentRunStatus.BUDGET_EXHAUSTED
    assert result.failure_code == "WALL_CLOCK_BUDGET_EXCEEDED"


def test_model_context_is_new_and_closed_for_each_sequential_run() -> None:
    """连续同步 Run 不得跨已关闭的 Event Loop 复用异步 Model Client。"""

    opened: list[asyncio.AbstractEventLoop] = []
    closed: list[asyncio.AbstractEventLoop] = []

    @asynccontextmanager
    async def model_context() -> AsyncIterator[FunctionModel]:
        loop = asyncio.get_running_loop()
        opened.append(loop)

        async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            del messages, info
            assert asyncio.get_running_loop() is loop
            return _text_response("ok")

        try:
            yield FunctionModel(respond, model_name="loop-fixture")
        finally:
            closed.append(asyncio.get_running_loop())

    runtime = PydanticAIRuntime(None, model_context_factory=model_context)

    assert runtime.run(_request()).status is AgentRunStatus.COMPLETED
    assert runtime.run(_request()).status is AgentRunStatus.COMPLETED
    assert len(opened) == len(closed) == 2
    assert opened == closed
    assert opened[0] is not opened[1]


def test_configured_runtime_creates_and_closes_provider_client_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production Factory 每次调用都关闭本次 Event Loop 中使用的 Client。"""

    opened: list[asyncio.AbstractEventLoop] = []
    closed: list[asyncio.AbstractEventLoop] = []
    client_timeouts: list[object] = []
    retry_limits: list[object] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            opened.append(asyncio.get_running_loop())
            client_timeouts.append(kwargs["timeout"])
            retry_limits.append(kwargs["max_retries"])

        async def close(self) -> None:
            closed.append(asyncio.get_running_loop())

    monkeypatch.setattr(pydantic_ai_runtime, "AsyncOpenAI", FakeClient)
    monkeypatch.setattr(
        pydantic_ai_runtime,
        "AlibabaProvider",
        lambda *, openai_client: openai_client,
    )
    monkeypatch.setattr(
        pydantic_ai_runtime,
        "OpenAIChatModel",
        lambda model_name, *, provider: FunctionModel(
            lambda messages, info: _text_response("ok"),
            model_name=model_name,
        ),
    )
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn("postgresql+psycopg://fixture.invalid/fixture"),
        llm_provider="ALIYUN_MODEL_STUDIO",
        llm_base_url=AnyHttpUrl("https://fixture.invalid/v1"),
        llm_api_key=SecretStr("fixture-key"),
        llm_model="fixture-model",
        llm_request_timeout_seconds=7,
        native_llm_request_timeout_seconds=60,
    )
    runtime = create_pydantic_ai_runtime(settings)

    assert runtime.timeout_seconds == 60
    assert runtime.run(_request()).status is AgentRunStatus.COMPLETED
    assert runtime.run(_request()).status is AgentRunStatus.COMPLETED
    assert len(opened) == len(closed) == 2
    assert opened == closed
    assert opened[0] is not opened[1]
    assert client_timeouts == [60, 60]
    assert retry_limits == [0, 0]


@pytest.mark.parametrize("timeout", [0, 61, float("inf")])
def test_native_request_timeout_cannot_exceed_approved_ceiling(timeout: float) -> None:
    """Native Provider 请求上限独立于旧 Runtime，并拒绝超过获批值。"""

    with pytest.raises(ValidationError, match="NATIVE_LLM_REQUEST_TIMEOUT_SECONDS"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url=PostgresDsn("postgresql+psycopg://fixture.invalid/fixture"),
            native_llm_request_timeout_seconds=timeout,
        )
