"""OpenAI Agents SDK Runtime 候选的离线 Capability 测试。"""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

import pytest
from agents import Tool
from agents.handoffs import Handoff
from agents.items import ModelResponse
from agents.model_settings import ModelSettings
from agents.models.interface import Model, ModelTracing
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from position_pilot.application.llm import LLMMessage, LLMRole, LLMToolDefinition

from .contracts import RuntimeBudget, RuntimeExecutionStatus, RuntimeInput, SourceRecord
from .current_runtime import FunctionToolExecutor, ToolObservation
from .openai_agents_runtime import OpenAIAgentsRuntimeCandidate
from .tool_catalog import CatalogTool, ToolCatalog, ToolCatalogError


@dataclass(slots=True)
class ScriptedAgentsModel(Model):
    """按顺序返回 SDK ModelResponse，并保存每轮可见 Tool。"""

    responses: list[ModelResponse]
    visible_tools: list[list[str]] = field(default_factory=list)
    instructions: list[str | None] = field(default_factory=list)
    inputs: list[str | list[Any]] = field(default_factory=list)

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> ModelResponse:
        """返回下一条离线响应。"""

        del model_settings, output_schema, handoffs, tracing
        del previous_response_id, conversation_id, prompt
        self.visible_tools.append([tool.name for tool in tools])
        self.instructions.append(system_instructions)
        self.inputs.append(input)
        return self.responses.pop(0)

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> AsyncIterator[Any]:
        """本 Spike 不使用 Streaming。"""

        del system_instructions, input, model_settings, tools, output_schema, handoffs, tracing
        del previous_response_id, conversation_id, prompt
        if False:
            yield None
        raise NotImplementedError


def _runtime_input() -> RuntimeInput:
    """创建最小 SDK Runtime 输入。"""

    return RuntimeInput(
        conversation=(LLMMessage(LLMRole.USER, "分析 GOOG"),),
        current_turn_context={"ticker": "GOOG", "budget": "500"},
        portfolio_context={"cash": "10000", "positions": ["GOOG"]},
        confirmed_strategy=({"scope": "GOOG", "plan": "分三次", "confirmed": True},),
        tools=(),
        budget=RuntimeBudget(4, 4, 2, 2, 30),
    )


def _text_response(text: str, *, usage: Usage | None = None) -> ModelResponse:
    """创建 SDK 文本响应。"""

    output_text = ResponseOutputText(
        annotations=[],
        text=text,
        type="output_text",
        logprobs=[],
    )
    message = ResponseOutputMessage(
        id="message-1",
        content=[output_text],
        role="assistant",
        status="completed",
        type="message",
    )
    return ModelResponse(
        output=[message],
        usage=usage or Usage(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
        response_id=None,
    )


def _tool_response(name: str, arguments: str, *, call_id: str = "call-1") -> ModelResponse:
    """创建 SDK Function Tool Call。"""

    tool_call = ResponseFunctionToolCall(
        arguments=arguments,
        call_id=call_id,
        name=name,
        type="function_call",
        id=f"item-{call_id}",
        status="completed",
    )
    return ModelResponse(
        output=[tool_call],
        usage=Usage(requests=1, input_tokens=8, output_tokens=3, total_tokens=11),
        response_id=None,
    )


def _definition(name: str, properties: Mapping[str, object]) -> LLMToolDefinition:
    """创建严格的只读 Tool Schema。"""

    return LLMToolDefinition(
        name,
        f"调用 {name}",
        {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    )


def test_no_tool_run_maps_usage_and_history() -> None:
    """SDK No-tool 路径保留 History、Strategy 与 Usage。"""

    model = ScriptedAgentsModel([_text_response("完成分析。")])
    runtime_input = replace(
        _runtime_input(),
        conversation=(
            LLMMessage(LLMRole.USER, "先看 GOOG"),
            LLMMessage(LLMRole.ASSISTANT, "先核验事实。"),
            LLMMessage(LLMRole.USER, "继续"),
        ),
    )

    result = OpenAIAgentsRuntimeCandidate(model, {}).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.usage is not None
    assert result.usage.total_tokens == 15
    assert model.visible_tools == [[]]
    assert "分三次" in (model.instructions[0] or "")


def test_dynamic_catalog_exposes_only_enabled_requested_tool() -> None:
    """同一 Catalog 只向本轮暴露启用且请求的自定义指标 Tool。"""

    calls: list[Mapping[str, object]] = []

    def indicator(arguments: Mapping[str, object]) -> ToolObservation:
        calls.append(arguments)
        return ToolObservation("OK", {"value": "42.0"})

    catalog = ToolCatalog(
        (
            CatalogTool(
                _definition(
                    "get_indicator_snapshot",
                    {"ticker": {"type": "string"}, "indicator": {"type": "string"}},
                ),
                FunctionToolExecutor(indicator),
            ),
            CatalogTool(
                _definition("disabled_plugin", {"ticker": {"type": "string"}}),
                FunctionToolExecutor(indicator),
                enabled=False,
            ),
        )
    )
    exposed = catalog.expose(("get_indicator_snapshot",))
    model = ScriptedAgentsModel(
        [
            _tool_response(
                "get_indicator_snapshot",
                '{"ticker":"GOOG","indicator":"RSI"}',
            ),
            _text_response("指标已读取。"),
        ]
    )
    runtime_input = replace(_runtime_input(), tools=exposed.definitions)

    result = OpenAIAgentsRuntimeCandidate(model, exposed.executors).run(runtime_input)

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert calls == [{"ticker": "GOOG", "indicator": "RSI"}]
    assert model.visible_tools == [
        ["get_indicator_snapshot"],
        ["get_indicator_snapshot"],
    ]
    assert [event.tool_name for event in result.tool_trace] == ["get_indicator_snapshot"]


def test_dynamic_catalog_rejects_disabled_and_unknown_tools() -> None:
    """禁用与未知 Tool 在进入 Framework 前被 Application 拒绝。"""

    executor = FunctionToolExecutor(lambda arguments: ToolObservation("OK", dict(arguments)))
    catalog = ToolCatalog((CatalogTool(_definition("disabled", {}), executor, enabled=False),))

    with pytest.raises(ToolCatalogError, match="DISABLED_TOOL"):
        catalog.expose(("disabled",))
    with pytest.raises(ToolCatalogError, match="UNKNOWN_TOOL"):
        catalog.expose(("missing",))


def test_multi_tool_source_registry_rejects_unobserved_final_reference() -> None:
    """SDK Tool 结果仍使用既有 Source Registry，不能引用虚构来源。"""

    search_definition = _definition("search_web", {"query": {"type": "string"}})
    fetch_definition = _definition("fetch_page", {"url": {"type": "string"}})
    observed_url = "https://example.test/filing"

    def search(_arguments: Mapping[str, object]) -> ToolObservation:
        return ToolObservation(
            "OK",
            {"url": observed_url},
            (SourceRecord("search-1", "FIXTURE", observed_url),),
        )

    def fetch(_arguments: Mapping[str, object]) -> ToolObservation:
        return ToolObservation(
            "OK",
            {"text": "正文"},
            (SourceRecord("fetch-1", "FIXTURE", observed_url),),
        )

    model = ScriptedAgentsModel(
        [
            _tool_response("search_web", '{"query":"GOOG filing"}', call_id="call-search"),
            _tool_response("fetch_page", f'{{"url":"{observed_url}"}}', call_id="call-fetch"),
            _text_response("来源：https://invented.example/report"),
        ]
    )
    result = OpenAIAgentsRuntimeCandidate(
        model,
        {
            "search_web": FunctionToolExecutor(search),
            "fetch_page": FunctionToolExecutor(fetch),
        },
    ).run(replace(_runtime_input(), tools=(search_definition, fetch_definition)))

    assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
    assert result.failure == "UNOBSERVED_SOURCE_REFERENCE"
    assert [event.tool_name for event in result.tool_trace] == ["search_web", "fetch_page"]
    assert len(result.model_trace) == 3
    assert result.usage is not None


def test_missing_provider_usage_stays_unknown() -> None:
    """Provider 未报告 Token 时不伪造零 Usage。"""

    model = ScriptedAgentsModel([_text_response("完成。", usage=Usage(requests=1))])

    result = OpenAIAgentsRuntimeCandidate(model, {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.usage is None
    assert result.warnings == ("USAGE_NOT_REPORTED",)


def test_provider_exception_is_safe_candidate_failure() -> None:
    """SDK Provider 异常不得泄露正文或伪造 Answer。"""

    model = ScriptedAgentsModel([])

    async def fail(*args: object, **kwargs: object) -> ModelResponse:
        del args, kwargs
        raise RuntimeError("secret provider body")

    model.get_response = fail  # type: ignore[method-assign]
    result = OpenAIAgentsRuntimeCandidate(model, {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
    assert result.answer is None
    assert result.failure == "OPENAI_AGENTS_CANDIDATE_FAILURE:RuntimeError"
