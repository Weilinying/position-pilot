"""OpenAI Agents SDK Runtime 候选的隔离 Capability Spike。"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import cast

from agents import Agent, FunctionTool, ModelSettings, RunConfig, Runner, Tool, TResponseInputItem
from agents.models.interface import Model
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from position_pilot.application.llm import LLMRole, LLMToolDefinition, LLMUsage

from .contracts import (
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
    SourceRecord,
    TraceEvent,
)
from .current_runtime import FETCH_TOOL_NAME, SEARCH_TOOL_NAME, ToolExecutor, ToolObservation
from .harness import (
    answer_source_failure,
    register_source,
    runtime_instructions,
    unresolved_tool_failure,
    untrusted_tool_payload,
)


def build_qwen_agents_model(
    model_name: str,
    *,
    api_key: str,
    base_url: str,
) -> OpenAIChatCompletionsModel:
    """使用 SDK 的 Chat Completions Adapter 接入当前 Qwen Endpoint。"""

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=0)
    return OpenAIChatCompletionsModel(
        model_name,
        openai_client=client,
        strict_feature_validation=True,
        buffer_streamed_tool_calls=False,
    )


@dataclass(slots=True)
class _AgentsToolBridge:
    """把 SDK Function Tool 薄接到 PositionPilot Spike Contract。"""

    executors: Mapping[str, ToolExecutor]
    runtime_input: RuntimeInput
    clock: Callable[[], float]
    started_at: float
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    trace: list[TraceEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seen_calls: set[str] = field(default_factory=set)
    tool_calls: int = 0
    search_calls: int = 0
    fetch_calls: int = 0
    budget_exhausted: bool = False

    def execute(self, name: str, arguments: Mapping[str, object]) -> str:
        """执行本轮已暴露 Tool，并保持预算与来源边界。"""

        if self._wall_clock_exhausted() or self.tool_calls >= self.runtime_input.budget.tool_calls:
            self.budget_exhausted = True
            return untrusted_tool_payload("BUDGET_EXHAUSTED", {}, ())
        self.tool_calls += 1
        key = json.dumps(
            {"name": name, "arguments": arguments},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if key in self.seen_calls:
            observation = ToolObservation("DUPLICATE_BLOCKED", {"reason": "REPEATED_TOOL_CALL"})
        else:
            self.seen_calls.add(key)
            observation = self._execute_once(name, arguments)
        if observation.status in {
            "INVALID_ARGUMENTS",
            "PARTIAL_SUCCESS",
            "TOOL_FAILURE",
            "UNKNOWN_TOOL",
        }:
            self.warnings.append(f"{observation.status}:{name}")
        for source in observation.sources:
            source_failure = register_source(self.sources, source)
            if source_failure is not None:
                self.warnings.append(source_failure)
                return untrusted_tool_payload("SOURCE_ID_CONFLICT", {}, ())
            self.trace.append(
                TraceEvent(
                    "tool-source",
                    len(self.trace) + 1,
                    observation.status,
                    name,
                    source.source_id,
                )
            )
        if not observation.sources:
            self.trace.append(TraceEvent("tool", len(self.trace) + 1, observation.status, name))
        if self._wall_clock_exhausted():
            self.budget_exhausted = True
        return untrusted_tool_payload(
            observation.status,
            observation.data,
            tuple(source.source_id for source in observation.sources),
        )

    def _execute_once(self, name: str, arguments: Mapping[str, object]) -> ToolObservation:
        """执行一次非重复调用，并分别限制 Search / Fetch。"""

        if name == SEARCH_TOOL_NAME:
            if self.search_calls >= self.runtime_input.budget.search_calls:
                self.budget_exhausted = True
                return ToolObservation("BUDGET_EXHAUSTED", {})
            self.search_calls += 1
        if name == FETCH_TOOL_NAME:
            if self.fetch_calls >= self.runtime_input.budget.fetch_calls:
                self.budget_exhausted = True
                return ToolObservation("BUDGET_EXHAUSTED", {})
            self.fetch_calls += 1
        executor = self.executors.get(name)
        if executor is None:
            return ToolObservation("UNKNOWN_TOOL", {"tool": name})
        try:
            return executor.execute(arguments)
        except (TypeError, ValueError) as exc:
            return ToolObservation("INVALID_ARGUMENTS", {"error_type": type(exc).__name__})
        except Exception as exc:  # noqa: BLE001 - Tool Failure 必须成为显式观察。
            return ToolObservation("TOOL_FAILURE", {"error_type": type(exc).__name__})

    def _wall_clock_exhausted(self) -> bool:
        """检查本次 Spike 的 Wall-clock Safety Ceiling。"""

        return self.clock() - self.started_at >= self.runtime_input.budget.wall_clock_seconds


class OpenAIAgentsRuntimeCandidate:
    """保留 OpenAI Agents SDK Runner 的最小候选。"""

    name = "openai-agents-sdk"

    def __init__(
        self,
        model: Model,
        tool_executors: Mapping[str, ToolExecutor],
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._model = model
        self._tool_executors = dict(tool_executors)
        self._clock = clock

    def run(self, runtime_input: RuntimeInput) -> RuntimeResult:
        """用 SDK 原生 Runner 执行同一 Provider-neutral 输入。"""

        started_at = self._clock()
        bridge = _AgentsToolBridge(self._tool_executors, runtime_input, self._clock, started_at)
        try:
            model_input = self._model_input(runtime_input)
            tools = self._tools(runtime_input.tools, bridge)
            agent: Agent[None] = Agent(
                name="PositionPilot Phase 3 Spike",
                instructions=runtime_instructions(runtime_input),
                model=self._model,
                tools=tools,
                model_settings=ModelSettings(
                    parallel_tool_calls=False,
                    preserve_raw_usage=True,
                    timeout=runtime_input.budget.wall_clock_seconds,
                ),
            )
            result = Runner.run_sync(
                agent,
                model_input,
                max_turns=runtime_input.budget.model_requests,
                run_config=RunConfig(tracing_disabled=True),
            )
        except ValueError as exc:
            return self._failure(
                "HARNESS_INPUT_UNSUPPORTED",
                started_at,
                bridge,
                type(exc).__name__,
            )
        except Exception as exc:  # noqa: BLE001 - SDK / Provider Failure 必须记录为候选结果。
            failure = (
                "OPENAI_AGENTS_REQUEST_LIMIT_EXCEEDED"
                if type(exc).__name__ == "MaxTurnsExceeded"
                else "OPENAI_AGENTS_CANDIDATE_FAILURE"
            )
            status = (
                RuntimeExecutionStatus.BUDGET_EXHAUSTED
                if type(exc).__name__ == "MaxTurnsExceeded"
                else RuntimeExecutionStatus.CANDIDATE_FAILURE
            )
            return self._failure(failure, started_at, bridge, type(exc).__name__, status=status)

        if bridge.budget_exhausted:
            return self._failure(
                "OPENAI_AGENTS_TOOL_BUDGET_EXHAUSTED",
                started_at,
                bridge,
                status=RuntimeExecutionStatus.BUDGET_EXHAUSTED,
            )
        if not isinstance(result.final_output, str) or not result.final_output.strip():
            return self._failure("INVALID_FINAL_OUTPUT", started_at, bridge)
        sources = tuple(bridge.sources.values())
        neutral_usage = self._map_usage(result.context_wrapper.usage)
        warnings = list(bridge.warnings)
        if neutral_usage is None:
            warnings.append("USAGE_NOT_REPORTED")
        model_trace = tuple(
            TraceEvent("model", sequence, "OK")
            for sequence in range(1, len(result.raw_responses) + 1)
        )
        final_failure = answer_source_failure(
            result.final_output, sources
        ) or unresolved_tool_failure(result.final_output, bridge.warnings)
        if final_failure is not None:
            return RuntimeResult(
                RuntimeExecutionStatus.CANDIDATE_FAILURE,
                None,
                final_failure,
                sources,
                model_trace,
                tuple(bridge.trace),
                neutral_usage,
                self._latency_ms(started_at),
                tuple(warnings),
            )
        return RuntimeResult(
            RuntimeExecutionStatus.COMPLETED,
            result.final_output,
            None,
            sources,
            model_trace,
            tuple(bridge.trace),
            neutral_usage,
            self._latency_ms(started_at),
            tuple(warnings),
        )

    @staticmethod
    def _model_input(runtime_input: RuntimeInput) -> list[TResponseInputItem]:
        """将受信 Conversation 映射为 SDK 可接受的 User / Assistant History。"""

        if (
            not runtime_input.conversation
            or runtime_input.conversation[-1].role is not LLMRole.USER
        ):
            raise ValueError("Conversation 必须以当前 User Message 结束")
        items: list[TResponseInputItem] = []
        for message in runtime_input.conversation:
            if message.role not in {LLMRole.USER, LLMRole.ASSISTANT} or message.content is None:
                raise ValueError("Spike History 只接受非空 User / Assistant Message")
            items.append(
                cast(
                    TResponseInputItem,
                    {"role": message.role.value, "content": message.content},
                )
            )
        return items

    @staticmethod
    def _tools(
        definitions: tuple[LLMToolDefinition, ...],
        bridge: _AgentsToolBridge,
    ) -> list[Tool]:
        """仅把 RuntimeInput 本轮暴露的 Tool 转成 SDK Function Tool。"""

        tools: list[Tool] = []
        for definition in definitions:

            async def invoke(
                _context: object,
                arguments_json: str,
                *,
                _tool_name: str = definition.name,
            ) -> str:
                """解析 SDK 参数并交给 Application-owned Executor。"""

                arguments = json.loads(arguments_json)
                if not isinstance(arguments, dict):
                    raise ValueError("Tool Arguments 必须是 object")
                return bridge.execute(_tool_name, arguments)

            tools.append(
                FunctionTool(
                    name=definition.name,
                    description=definition.description,
                    params_json_schema=dict(definition.parameters),
                    on_invoke_tool=invoke,
                    strict_json_schema=False,
                )
            )
        return tools

    @staticmethod
    def _map_usage(usage: object) -> LLMUsage | None:
        """把 SDK Usage 映射为现有 Contract，缺失时保持 UNKNOWN。"""

        requests = getattr(usage, "requests", 0)
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)
        if requests > 0 and input_tokens == 0 and output_tokens == 0 and total_tokens == 0:
            return None
        return LLMUsage(input_tokens, output_tokens, total_tokens)

    def _latency_ms(self, started_at: float) -> float:
        """记录候选总耗时。"""

        return max(0.0, (self._clock() - started_at) * 1000)

    def _failure(
        self,
        failure: str,
        started_at: float,
        bridge: _AgentsToolBridge,
        detail: str | None = None,
        *,
        status: RuntimeExecutionStatus = RuntimeExecutionStatus.CANDIDATE_FAILURE,
    ) -> RuntimeResult:
        """候选失败不生成 Answer，也不泄露异常正文。"""

        safe_failure = failure if detail is None else f"{failure}:{detail}"
        return RuntimeResult(
            status,
            None,
            safe_failure,
            tuple(bridge.sources.values()),
            (),
            tuple(bridge.trace),
            None,
            self._latency_ms(started_at),
            tuple(bridge.warnings),
        )
