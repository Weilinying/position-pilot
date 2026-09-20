"""Phase 3 使用的最小 Application-owned Runtime 候选。"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
    LLMUsage,
)

from .contracts import (
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
    SourceRecord,
    TraceEvent,
)
from .harness import (
    answer_source_failure,
    register_source,
    runtime_instructions,
    unresolved_tool_failure,
    untrusted_tool_payload,
)

SEARCH_TOOL_NAME = "search_web"
FETCH_TOOL_NAME = "fetch_page"
READ_ONLY_TOOL_NAMES = frozenset({"get_current_quote", SEARCH_TOOL_NAME, FETCH_TOOL_NAME})


@dataclass(frozen=True, slots=True)
class ToolObservation:
    """Tool Executor 返回给 Runtime 的结构化观察。"""

    status: str
    data: Mapping[str, object]
    sources: tuple[SourceRecord, ...] = ()

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("Tool Observation status 不能为空")
        if self.sources and self.status not in {"OK", "PARTIAL_SUCCESS"}:
            raise ValueError("只有成功或部分成功的 Tool Observation 可以包含来源")


class ToolExecutor(Protocol):
    """Spike Tool 的最小执行接口。"""

    def execute(self, arguments: Mapping[str, object]) -> ToolObservation: ...


@dataclass(frozen=True, slots=True)
class FunctionToolExecutor:
    """将简单函数适配为 Tool Executor。"""

    function: Callable[[Mapping[str, object]], ToolObservation]

    def execute(self, arguments: Mapping[str, object]) -> ToolObservation:
        """执行显式注册的函数。"""

        return self.function(arguments)


class CurrentRuntimeCandidate:
    """只为 Capability Spike 实现的最小多轮循环。"""

    name = "current"

    def __init__(
        self,
        llm: LLMProvider,
        tool_executors: Mapping[str, ToolExecutor],
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._llm = llm
        self._tool_executors = dict(tool_executors)
        self._clock = clock

    def run(self, runtime_input: RuntimeInput) -> RuntimeResult:
        """执行有限循环；所有状态写入能力均来自显式 Tool Allowlist。"""

        started_at = self._clock()
        messages = [self._context_message(runtime_input), *runtime_input.conversation]
        model_trace: list[TraceEvent] = []
        tool_trace: list[TraceEvent] = []
        sources: dict[str, SourceRecord] = {}
        usages: list[LLMUsage] = []
        seen_calls: set[str] = set()
        safe_tools = tuple(
            tool for tool in runtime_input.tools if tool.name in READ_ONLY_TOOL_NAMES
        )
        allowed_tools = {tool.name: tool for tool in safe_tools}
        model_requests = 0
        tool_calls = 0
        search_calls = 0
        fetch_calls = 0
        warnings: list[str] = []

        while True:
            if self._clock() - started_at >= runtime_input.budget.wall_clock_seconds:
                return self._failure(
                    RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                    "WALL_CLOCK_BUDGET_EXHAUSTED",
                    started_at,
                    model_trace,
                    tool_trace,
                    tuple(sources.values()),
                    usages,
                    warnings,
                )
            if model_requests >= runtime_input.budget.model_requests:
                return self._failure(
                    RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                    "MODEL_REQUEST_BUDGET_EXHAUSTED",
                    started_at,
                    model_trace,
                    tool_trace,
                    tuple(sources.values()),
                    usages,
                    warnings,
                )

            model_requests += 1
            result = self._llm.complete(tuple(messages), tools=safe_tools)
            if result.metadata is not None and result.metadata.usage is not None:
                usages.append(result.metadata.usage)
            model_trace.append(
                TraceEvent(
                    "model",
                    model_requests,
                    result.status.value,
                )
            )
            if self._wall_clock_exhausted(started_at, runtime_input):
                return self._failure(
                    RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                    "WALL_CLOCK_BUDGET_EXHAUSTED",
                    started_at,
                    model_trace,
                    tool_trace,
                    tuple(sources.values()),
                    usages,
                    warnings,
                )
            if result.status is not LLMStatus.OK or result.completion is None:
                return self._failure(
                    RuntimeExecutionStatus.CANDIDATE_FAILURE,
                    result.error_message or "LLM_PROVIDER_FAILURE",
                    started_at,
                    model_trace,
                    tool_trace,
                    tuple(sources.values()),
                    usages,
                    warnings,
                )

            assistant = result.completion.message
            messages.append(assistant)
            if not assistant.tool_calls:
                if assistant.content is None:
                    return self._failure(
                        RuntimeExecutionStatus.CANDIDATE_FAILURE,
                        "EMPTY_FINAL_ANSWER",
                        started_at,
                        model_trace,
                        tool_trace,
                        tuple(sources.values()),
                        usages,
                        warnings,
                    )
                citation_failure = answer_source_failure(
                    assistant.content,
                    tuple(sources.values()),
                )
                final_failure = citation_failure or unresolved_tool_failure(
                    assistant.content,
                    warnings,
                )
                if final_failure is not None:
                    return self._failure(
                        RuntimeExecutionStatus.CANDIDATE_FAILURE,
                        final_failure,
                        started_at,
                        model_trace,
                        tool_trace,
                        tuple(sources.values()),
                        usages,
                        warnings,
                    )
                return RuntimeResult(
                    RuntimeExecutionStatus.COMPLETED,
                    assistant.content,
                    None,
                    tuple(sources.values()),
                    tuple(model_trace),
                    tuple(tool_trace),
                    self._aggregate_usage(usages, model_requests),
                    self._latency_ms(started_at),
                    tuple(warnings),
                )

            for tool_call in assistant.tool_calls:
                if tool_calls >= runtime_input.budget.tool_calls:
                    return self._failure(
                        RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                        "TOOL_CALL_BUDGET_EXHAUSTED",
                        started_at,
                        model_trace,
                        tool_trace,
                        tuple(sources.values()),
                        usages,
                        warnings,
                    )
                duplicate = self._tool_call_key(tool_call) in seen_calls
                if tool_call.name == SEARCH_TOOL_NAME and not duplicate:
                    if search_calls >= runtime_input.budget.search_calls:
                        return self._failure(
                            RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                            "SEARCH_BUDGET_EXHAUSTED",
                            started_at,
                            model_trace,
                            tool_trace,
                            tuple(sources.values()),
                            usages,
                            warnings,
                        )
                    search_calls += 1
                if tool_call.name == FETCH_TOOL_NAME and not duplicate:
                    if fetch_calls >= runtime_input.budget.fetch_calls:
                        return self._failure(
                            RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                            "FETCH_BUDGET_EXHAUSTED",
                            started_at,
                            model_trace,
                            tool_trace,
                            tuple(sources.values()),
                            usages,
                            warnings,
                        )
                    fetch_calls += 1

                tool_calls += 1
                observation = self._execute_tool(tool_call, seen_calls, allowed_tools)
                if observation.status in {
                    "INVALID_ARGUMENTS",
                    "PARTIAL_SUCCESS",
                    "TOOL_FAILURE",
                    "UNKNOWN_TOOL",
                }:
                    warnings.append(f"{observation.status}:{tool_call.name}")
                for source in observation.sources:
                    source_failure = register_source(sources, source)
                    if source_failure is not None:
                        return self._failure(
                            RuntimeExecutionStatus.CANDIDATE_FAILURE,
                            source_failure,
                            started_at,
                            model_trace,
                            tool_trace,
                            tuple(sources.values()),
                            usages,
                            warnings,
                        )
                    tool_trace.append(
                        TraceEvent(
                            "tool-source",
                            len(tool_trace) + 1,
                            observation.status,
                            tool_call.name,
                            source.source_id,
                        )
                    )
                if not observation.sources:
                    tool_trace.append(
                        TraceEvent(
                            "tool",
                            len(tool_trace) + 1,
                            observation.status,
                            tool_call.name,
                        )
                    )
                messages.append(
                    LLMMessage(
                        LLMRole.TOOL,
                        self._observation_payload(observation),
                        tool_call_id=tool_call.id,
                    )
                )
                if self._wall_clock_exhausted(started_at, runtime_input):
                    return self._failure(
                        RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                        "WALL_CLOCK_BUDGET_EXHAUSTED",
                        started_at,
                        model_trace,
                        tool_trace,
                        tuple(sources.values()),
                        usages,
                        warnings,
                    )

    def _execute_tool(
        self,
        tool_call: LLMToolCall,
        seen_calls: set[str],
        allowed_tools: Mapping[str, LLMToolDefinition],
    ) -> ToolObservation:
        """只执行注册 Tool，并阻止完全相同的重复调用。"""

        call_key = self._tool_call_key(tool_call)
        if call_key in seen_calls:
            return ToolObservation("DUPLICATE_BLOCKED", {"reason": "REPEATED_TOOL_CALL"})
        seen_calls.add(call_key)
        definition = allowed_tools.get(tool_call.name)
        if definition is None:
            return ToolObservation("UNKNOWN_TOOL", {"tool": tool_call.name})
        validation_error = self._validate_arguments(definition, tool_call.arguments)
        if validation_error is not None:
            return ToolObservation("INVALID_ARGUMENTS", {"reason": validation_error})
        executor = self._tool_executors.get(tool_call.name)
        if executor is None:
            return ToolObservation("UNKNOWN_TOOL", {"tool": tool_call.name})
        try:
            return executor.execute(tool_call.arguments)
        except (TypeError, ValueError) as exc:
            return ToolObservation("INVALID_ARGUMENTS", {"error_type": type(exc).__name__})
        except Exception as exc:  # noqa: BLE001 - Provider / Tool Failure 必须成为显式观察。
            return ToolObservation("TOOL_FAILURE", {"error_type": type(exc).__name__})

    @staticmethod
    def _tool_call_key(tool_call: LLMToolCall) -> str:
        """生成重复调用识别键；非 JSON 参数属于无效 Tool Call。"""

        try:
            return json.dumps(
                {"name": tool_call.name, "arguments": tool_call.arguments},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            return f"INVALID_ARGUMENTS:{tool_call.id}"

    @staticmethod
    def _validate_arguments(
        definition: LLMToolDefinition,
        arguments: Mapping[str, object],
    ) -> str | None:
        """验证 Spike 使用的最小 JSON Schema object 子集。"""

        schema = definition.parameters
        if schema.get("type") != "object":
            return "UNSUPPORTED_TOOL_SCHEMA"
        properties = schema.get("properties", {})
        required = schema.get("required", ())
        if not isinstance(properties, Mapping) or not isinstance(required, (list, tuple)):
            return "INVALID_TOOL_SCHEMA"
        if any(not isinstance(name, str) for name in required):
            return "INVALID_TOOL_SCHEMA"
        missing = sorted(name for name in required if name not in arguments)
        if missing:
            return f"MISSING_REQUIRED:{','.join(missing)}"
        if schema.get("additionalProperties") is False:
            extra = sorted(name for name in arguments if name not in properties)
            if extra:
                return f"UNEXPECTED_ARGUMENT:{','.join(extra)}"
        expected_types: dict[str, type[object] | tuple[type[object], ...]] = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": Mapping,
            "array": (list, tuple),
        }
        for name, value in arguments.items():
            property_schema = properties.get(name)
            if not isinstance(property_schema, Mapping):
                continue
            expected_name = property_schema.get("type")
            expected = expected_types.get(expected_name) if isinstance(expected_name, str) else None
            if expected is not None and (
                isinstance(value, bool) and expected_name in {"number", "integer"}
            ):
                return f"INVALID_TYPE:{name}"
            if expected is not None and not isinstance(value, expected):
                return f"INVALID_TYPE:{name}"
        return None

    def _wall_clock_exhausted(self, started_at: float, runtime_input: RuntimeInput) -> bool:
        """在每次外部调用前后检查总 Wall-clock Ceiling。"""

        return self._clock() - started_at >= runtime_input.budget.wall_clock_seconds

    @staticmethod
    def _context_message(runtime_input: RuntimeInput) -> LLMMessage:
        """将五类输入边界显式放入 System Context。"""

        return LLMMessage(LLMRole.SYSTEM, runtime_instructions(runtime_input))

    @staticmethod
    def _observation_payload(observation: ToolObservation) -> str:
        """以数据边界包装 Tool 内容，避免将外部文本提升为指令。"""

        return untrusted_tool_payload(
            observation.status,
            observation.data,
            tuple(source.source_id for source in observation.sources),
        )

    @staticmethod
    def _aggregate_usage(usages: list[LLMUsage], model_requests: int) -> LLMUsage | None:
        """只有每次请求都有 Usage 时才汇总。"""

        if len(usages) != model_requests:
            return None
        return LLMUsage(
            sum(usage.input_tokens for usage in usages),
            sum(usage.output_tokens for usage in usages),
            sum(usage.total_tokens for usage in usages),
        )

    def _latency_ms(self, started_at: float) -> float:
        """记录候选总耗时。"""

        return max(0.0, (self._clock() - started_at) * 1000)

    def _failure(
        self,
        status: RuntimeExecutionStatus,
        failure: str,
        started_at: float,
        model_trace: list[TraceEvent],
        tool_trace: list[TraceEvent],
        sources: tuple[SourceRecord, ...],
        usages: list[LLMUsage],
        warnings: list[str],
    ) -> RuntimeResult:
        """失败不生成伪造 Answer，并保留已经取得的有效来源。"""

        return RuntimeResult(
            status,
            None,
            failure,
            sources,
            tuple(model_trace),
            tuple(tool_trace),
            self._aggregate_usage(usages, len(model_trace)),
            self._latency_ms(started_at),
            tuple(warnings),
        )
