"""PydanticAI Runtime 候选的离线 Capability 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import SimpleNamespace

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.llm import (
    LLMMessage,
    LLMRole,
    LLMToolDefinition,
)

from .contracts import RuntimeBudget, RuntimeExecutionStatus, RuntimeInput, SourceRecord
from .current_runtime import FunctionToolExecutor, ToolObservation
from .harness import canonical_input_hash
from .pydantic_runtime import PydanticRuntimeCandidate, build_alibaba_chat_model
from .tool_catalog import CatalogTool, ToolCatalog


@dataclass(slots=True)
class ScriptedModel:
    """按顺序返回 PydanticAI ModelResponse，并保存框架消息。"""

    responses: list[ModelResponse]
    calls: list[list[ModelMessage]] = field(default_factory=list)
    infos: list[AgentInfo] = field(default_factory=list)

    def __call__(
        self,
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        """返回下一条离线响应。"""

        self.calls.append(list(messages))
        self.infos.append(info)
        return self.responses.pop(0)


def _runtime_input(*, budget: RuntimeBudget | None = None) -> RuntimeInput:
    """创建与 Current Runtime 测试语义相同的固定输入。"""

    return RuntimeInput(
        conversation=(
            LLMMessage(LLMRole.USER, "先分析 GOOG"),
            LLMMessage(LLMRole.ASSISTANT, "我会先核验当前事实。"),
            LLMMessage(LLMRole.USER, "本轮预算改为 500 美元，继续。"),
        ),
        current_turn_context={"ticker": "GOOG", "budget": "500"},
        portfolio_context={"cash": "10000", "positions": ["GOOG"]},
        confirmed_strategy=({"scope": "GOOG", "plan": "分三次", "confirmed": True},),
        tools=(
            LLMToolDefinition(
                "get_current_quote",
                "读取报价",
                {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            LLMToolDefinition(
                "search_web",
                "搜索公开信息",
                {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            ),
            LLMToolDefinition(
                "fetch_page",
                "读取公开页面",
                {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
            ),
        ),
        budget=budget or RuntimeBudget(4, 4, 2, 2, 30),
    )


def _model(script: ScriptedModel) -> FunctionModel:
    """把脚本包装为 PydanticAI 官方离线 Model。"""

    def scripted_model(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        """使用具名函数满足 FunctionModel 的诊断名称要求。"""

        return script(messages, info)

    return FunctionModel(scripted_model, model_name="qwen3.7-max-fixture")


def _text_response(content: str) -> ModelResponse:
    """创建文本响应。"""

    return ModelResponse(parts=(TextPart(content),), model_name="qwen3.7-max-fixture")


def _tool_response(name: str, arguments: Mapping[str, object]) -> ModelResponse:
    """创建 Tool Call 响应。"""

    return ModelResponse(
        parts=(ToolCallPart(name, dict(arguments), "call-1"),),
        model_name="qwen3.7-max-fixture",
    )


def test_pydantic_runtime_uses_native_history_and_shared_context() -> None:
    """框架原生 History 保持 Conversation 顺序，并接收同语义 Context。"""

    script = ScriptedModel([_text_response("条件分析完成。")])
    runtime_input = _runtime_input()
    before_hash = canonical_input_hash(runtime_input)

    result = PydanticRuntimeCandidate(_model(script), {}).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.answer == "条件分析完成。"
    assert canonical_input_hash(runtime_input) == before_hash
    assert len(script.calls) == 1
    messages = script.calls[0]
    assert isinstance(messages[0], ModelRequest)
    assert isinstance(messages[0].parts[0], UserPromptPart)
    assert messages[0].parts[0].content == "先分析 GOOG"
    assert isinstance(messages[1], ModelResponse)
    assistant_part = messages[1].parts[0]
    assert isinstance(assistant_part, TextPart)
    assert assistant_part.content == "我会先核验当前事实。"
    assert isinstance(messages[-1], ModelRequest)
    request_text = " ".join(
        part.content
        for part in messages[-1].parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    )
    assert "本轮预算改为 500 美元" in request_text
    instructions = script.infos[0].instructions
    assert instructions is not None
    assert '"budget":"500"' in instructions
    assert '"plan":"分三次"' in instructions


def test_pydantic_runtime_uses_native_tool_loop_and_records_source() -> None:
    """原生 Tool Loop 经过薄 Bridge，并保留来源、Usage 与不可信边界。"""

    script = ScriptedModel(
        [
            _tool_response("get_current_quote", {"ticker": "GOOG"}),
            _text_response("当前报价已核验。[source:quote-1]"),
        ]
    )
    source = SourceRecord("quote-1", "FAKE_MARKET", None)
    quote = FunctionToolExecutor(
        lambda arguments: ToolObservation(
            "OK",
            {"ticker": arguments["ticker"], "price": "210.25"},
            (source,),
        )
    )

    result = PydanticRuntimeCandidate(
        _model(script),
        {"get_current_quote": quote},
    ).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.sources == (source,)
    assert len(result.model_trace) == 2
    assert result.tool_trace[0].source_id == "quote-1"
    assert result.usage is not None
    assert result.usage.input_tokens > 0
    assert result.usage.total_tokens >= result.usage.input_tokens
    second_call = script.calls[1]
    serialized_messages = repr(second_call)
    assert "UNTRUSTED_TOOL_DATA" in serialized_messages
    assert "quote-1" in serialized_messages


def test_pydantic_runtime_completes_multi_round_search_and_fetch() -> None:
    """PydanticAI 原生 Loop 支持 Search → Fetch → Final 的 2+ Tool 场景。"""

    script = ScriptedModel(
        [
            _tool_response("search_web", {"query": "GOOG latest filing"}),
            ModelResponse(
                parts=(
                    ToolCallPart(
                        "fetch_page",
                        {"url": "https://example.test/filing"},
                        "call-2",
                    ),
                )
            ),
            _text_response("已核验搜索与原文。[source:search-1] [source:fetch-1]"),
        ]
    )
    search = FunctionToolExecutor(
        lambda arguments: ToolObservation(
            "OK",
            {"query": arguments["query"]},
            (SourceRecord("search-1", "FAKE_SEARCH", "https://example.test/filing"),),
        )
    )
    fetch = FunctionToolExecutor(
        lambda arguments: ToolObservation(
            "OK",
            {"url": arguments["url"], "text": "公开文件正文"},
            (SourceRecord("fetch-1", "FAKE_FETCH", "https://example.test/filing"),),
        )
    )

    result = PydanticRuntimeCandidate(
        _model(script),
        {"search_web": search, "fetch_page": fetch},
    ).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert [event.tool_name for event in result.tool_trace] == ["search_web", "fetch_page"]
    assert [source.source_id for source in result.sources] == ["search-1", "fetch-1"]
    assert len(result.model_trace) == 3


def test_pydantic_runtime_rejects_unobserved_source_reference() -> None:
    """模型不得凭空输出本轮未观察到的来源。"""

    script = ScriptedModel([_text_response("请见 https://invented.test/source")])

    result = PydanticRuntimeCandidate(_model(script), {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
    assert result.failure == "UNOBSERVED_SOURCE_REFERENCE"
    assert result.answer is None
    assert len(result.model_trace) == 1
    assert result.usage is not None


def test_pydantic_runtime_preserves_tool_failure_as_warning() -> None:
    """Tool Adapter 失败是显式观察，不直接判定框架架构不支持。"""

    script = ScriptedModel(
        [
            _tool_response("get_current_quote", {"ticker": "GOOG"}),
            _text_response("报价 Provider 当前不可用，因此保持 UNKNOWN。"),
        ]
    )

    def fail(arguments: Mapping[str, object]) -> ToolObservation:
        """模拟受控 Tool Provider Failure。"""

        del arguments
        raise RuntimeError("provider unavailable")

    result = PydanticRuntimeCandidate(
        _model(script),
        {"get_current_quote": FunctionToolExecutor(fail)},
    ).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.warnings == ("TOOL_FAILURE:get_current_quote",)
    assert result.sources == ()


def test_pydantic_runtime_rejects_definite_answer_after_tool_failure() -> None:
    """框架候选不能在 Tool Failure 后输出无保留的确定事实。"""

    script = ScriptedModel(
        [
            _tool_response("get_current_quote", {"ticker": "GOOG"}),
            _text_response("GOOG 当前价格确定为 210.25 美元。"),
        ]
    )

    def fail(arguments: Mapping[str, object]) -> ToolObservation:
        del arguments
        raise RuntimeError("provider unavailable")

    result = PydanticRuntimeCandidate(
        _model(script),
        {"get_current_quote": FunctionToolExecutor(fail)},
    ).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
    assert result.failure == "UNRESOLVED_TOOL_FAILURE"


def test_pydantic_runtime_rejects_conflicting_source_identity() -> None:
    """Pydantic Tool Bridge 也不得静默覆盖重复 Source ID。"""

    script = ScriptedModel([_tool_response("get_current_quote", {"ticker": "GOOG"})])
    quote = FunctionToolExecutor(
        lambda arguments: ToolObservation(
            "OK",
            {"ticker": arguments["ticker"]},
            (
                SourceRecord("source-1", "FAKE", "https://example.test/one"),
                SourceRecord("source-1", "FAKE", "https://example.test/two"),
            ),
        )
    )

    result = PydanticRuntimeCandidate(
        _model(script),
        {"get_current_quote": quote},
    ).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
    assert result.answer is None
    assert "SOURCE_ID_CONFLICT" in result.warnings


def test_pydantic_runtime_stops_at_native_request_limit() -> None:
    """框架原生 UsageLimits 在额外 Model Request 前停止循环。"""

    script = ScriptedModel(
        [
            _tool_response("get_current_quote", {"ticker": "GOOG"}),
            _text_response("不应执行到这里。"),
        ]
    )
    quote = FunctionToolExecutor(
        lambda arguments: ToolObservation("OK", {"ticker": arguments["ticker"]})
    )
    runtime_input = replace(
        _runtime_input(),
        budget=RuntimeBudget(1, 2, 1, 1, 30),
    )

    result = PydanticRuntimeCandidate(
        _model(script),
        {"get_current_quote": quote},
    ).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.BUDGET_EXHAUSTED
    assert result.failure == "PYDANTIC_USAGE_LIMIT_EXCEEDED"
    assert len(script.calls) == 1


def test_dynamic_schema_tool_closes_the_previous_bridge_gap() -> None:
    """通用 JSON Schema Adapter 可正常暴露此前未硬编码的 Tool。"""

    runtime_input = replace(
        _runtime_input(),
        tools=(
            LLMToolDefinition(
                "calculate_scenario",
                "计算情景",
                {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
        ),
    )

    calls: list[Mapping[str, object]] = []

    def calculate(arguments: Mapping[str, object]) -> ToolObservation:
        """记录动态 Tool 参数。"""

        calls.append(arguments)
        return ToolObservation("OK", {"value": "42"})

    executor = FunctionToolExecutor(calculate)
    result = PydanticRuntimeCandidate(
        _model(
            ScriptedModel([_tool_response("calculate_scenario", {}), _text_response("已计算。")])
        ),
        {"calculate_scenario": executor},
    ).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert calls == [{}]


def test_application_catalog_limits_pydantic_visible_tools() -> None:
    """PydanticAI 只看到 Application 本轮启用并选择的 Tool。"""

    calls: list[Mapping[str, object]] = []

    def indicator(arguments: Mapping[str, object]) -> ToolObservation:
        """记录动态指标 Tool 参数。"""

        calls.append(arguments)
        return ToolObservation("OK", {"value": "42.0"})

    definition = LLMToolDefinition(
        "get_indicator_snapshot",
        "读取指标快照",
        {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    )
    disabled = LLMToolDefinition(
        "disabled_plugin",
        "禁用插件",
        {"type": "object", "properties": {}, "additionalProperties": False},
    )
    executor = FunctionToolExecutor(indicator)
    catalog = ToolCatalog(
        (
            CatalogTool(definition, executor),
            CatalogTool(disabled, executor, enabled=False),
        )
    )
    exposed = catalog.expose(("get_indicator_snapshot",))
    script = ScriptedModel(
        [
            _tool_response("get_indicator_snapshot", {"ticker": "GOOG"}),
            _text_response("指标已读取。"),
        ]
    )
    runtime_input = replace(_runtime_input(), tools=exposed.definitions)

    result = PydanticRuntimeCandidate(_model(script), exposed.executors).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert calls == [{"ticker": "GOOG"}]
    assert [tool.name for tool in script.infos[0].function_tools] == ["get_indicator_snapshot"]


def test_missing_provider_usage_stays_unknown() -> None:
    """Provider 未报告 Token 时不把全零 Usage 当作真实测量。"""

    usage = SimpleNamespace(requests=1, input_tokens=0, output_tokens=0)

    assert PydanticRuntimeCandidate._map_usage(usage) is None


def test_alibaba_provider_builder_uses_native_provider() -> None:
    """Provider Smoke 证明无需额外 OpenAI-compatible Bridge。"""

    model = build_alibaba_chat_model(
        "qwen3.7-max",
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    assert model.model_name == "qwen3.7-max"
    assert model.system == "alibaba"
