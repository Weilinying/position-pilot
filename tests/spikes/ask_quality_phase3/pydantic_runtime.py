"""PydanticAI Runtime 候选与 Alibaba Provider 最小接线。"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic

from pydantic_ai import Agent, FunctionToolset, UsageLimitExceeded, UsageLimits
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.alibaba import AlibabaProvider

from position_pilot.application.llm import LLMRole, LLMToolDefinition, LLMUsage

from .contracts import (
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
    SourceRecord,
    TraceEvent,
)
from .current_runtime import (
    FETCH_TOOL_NAME,
    SEARCH_TOOL_NAME,
    ToolExecutor,
    ToolObservation,
)
from .harness import answer_source_failure, runtime_instructions, untrusted_tool_payload


def build_alibaba_chat_model(
    model_name: str,
    *,
    api_key: str,
    base_url: str,
) -> OpenAIChatModel:
    """通过 PydanticAI 原生 AlibabaProvider 构造 Chat Model。"""

    return OpenAIChatModel(
        model_name,
        provider=AlibabaProvider(api_key=api_key, base_url=base_url),
    )


@dataclass(slots=True)
class _ToolBridge:
    """将 PydanticAI Function Tool 薄接到现有 Spike Tool Executor。"""

    executors: Mapping[str, ToolExecutor]
    runtime_input: RuntimeInput
    clock: Callable[[], float]
    started_at: float
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    trace: list[TraceEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seen_calls: set[str] = field(default_factory=set)
    search_calls: int = 0
    fetch_calls: int = 0

    def execute(self, name: str, arguments: Mapping[str, object]) -> str:
        """执行 Tool，并保留预算、重复、来源和失败状态。"""

        if self.clock() - self.started_at >= self.runtime_input.budget.wall_clock_seconds:
            raise UsageLimitExceeded("wall-clock budget exhausted")
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
            if name == SEARCH_TOOL_NAME:
                if self.search_calls >= self.runtime_input.budget.search_calls:
                    raise UsageLimitExceeded("search budget exhausted")
                self.search_calls += 1
            if name == FETCH_TOOL_NAME:
                if self.fetch_calls >= self.runtime_input.budget.fetch_calls:
                    raise UsageLimitExceeded("fetch budget exhausted")
                self.fetch_calls += 1
            executor = self.executors.get(name)
            if executor is None:
                observation = ToolObservation("UNKNOWN_TOOL", {"tool": name})
            else:
                try:
                    observation = executor.execute(arguments)
                except (TypeError, ValueError) as exc:
                    observation = ToolObservation(
                        "INVALID_ARGUMENTS",
                        {"error_type": type(exc).__name__},
                    )
                except Exception as exc:  # noqa: BLE001 - Tool Failure 必须成为显式观察。
                    observation = ToolObservation(
                        "TOOL_FAILURE",
                        {"error_type": type(exc).__name__},
                    )
        if observation.status in {
            "INVALID_ARGUMENTS",
            "PARTIAL_SUCCESS",
            "TOOL_FAILURE",
            "UNKNOWN_TOOL",
        }:
            self.warnings.append(f"{observation.status}:{name}")
        if observation.sources:
            for source in observation.sources:
                self.sources[source.source_id] = source
                self.trace.append(
                    TraceEvent(
                        "tool-source",
                        len(self.trace) + 1,
                        observation.status,
                        name,
                        source.source_id,
                    )
                )
        else:
            self.trace.append(TraceEvent("tool", len(self.trace) + 1, observation.status, name))
        if self.clock() - self.started_at >= self.runtime_input.budget.wall_clock_seconds:
            raise UsageLimitExceeded("wall-clock budget exhausted")
        return untrusted_tool_payload(
            observation.status,
            observation.data,
            tuple(source.source_id for source in observation.sources),
        )


class PydanticRuntimeCandidate:
    """保留 PydanticAI 原生 Agent Loop 的最小候选。"""

    name = "pydantic-ai"

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
        """使用框架原生 History、Tool Loop 与 UsageLimits 执行同一输入。"""

        started_at = self._clock()
        try:
            history, user_prompt = self._message_history(runtime_input)
            bridge = _ToolBridge(self._tool_executors, runtime_input, self._clock, started_at)
            toolset = self._toolset(runtime_input.tools, bridge)
        except ValueError as exc:
            return self._failure(
                "HARNESS_INPUT_UNSUPPORTED",
                started_at,
                failure_detail=type(exc).__name__,
            )

        agent = Agent(
            self._model,
            output_type=str,
            instructions=runtime_instructions(runtime_input),
            toolsets=(() if toolset is None else (toolset,)),
            retries=0,
            end_strategy="exhaustive",
        )
        try:
            result = agent.run_sync(
                user_prompt,
                message_history=history,
                usage_limits=UsageLimits(
                    request_limit=runtime_input.budget.model_requests,
                    tool_calls_limit=runtime_input.budget.tool_calls,
                ),
            )
        except UsageLimitExceeded:
            return RuntimeResult(
                RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                None,
                "PYDANTIC_USAGE_LIMIT_EXCEEDED",
                tuple(bridge.sources.values()),
                (),
                tuple(bridge.trace),
                None,
                self._latency_ms(started_at),
                tuple(bridge.warnings),
            )
        except Exception as exc:  # noqa: BLE001 - Framework / Provider Failure 必须记录为候选结果。
            return self._failure(
                "PYDANTIC_CANDIDATE_FAILURE",
                started_at,
                bridge=bridge,
                failure_detail=type(exc).__name__,
            )

        if self._clock() - started_at >= runtime_input.budget.wall_clock_seconds:
            return RuntimeResult(
                RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                None,
                "WALL_CLOCK_BUDGET_EXHAUSTED",
                tuple(bridge.sources.values()),
                (),
                tuple(bridge.trace),
                None,
                self._latency_ms(started_at),
                tuple(bridge.warnings),
            )
        sources = tuple(bridge.sources.values())
        citation_failure = answer_source_failure(result.output, sources)
        if citation_failure is not None:
            return self._failure(
                citation_failure,
                started_at,
                bridge=bridge,
            )
        usage = result.usage
        neutral_usage = LLMUsage(
            usage.input_tokens,
            usage.output_tokens,
            usage.input_tokens + usage.output_tokens,
        )
        model_trace = tuple(
            TraceEvent("model", sequence, "OK") for sequence in range(1, usage.requests + 1)
        )
        return RuntimeResult(
            RuntimeExecutionStatus.COMPLETED,
            result.output,
            None,
            sources,
            model_trace,
            tuple(bridge.trace),
            neutral_usage,
            self._latency_ms(started_at),
            tuple(bridge.warnings),
        )

    @staticmethod
    def _message_history(
        runtime_input: RuntimeInput,
    ) -> tuple[list[ModelMessage], str]:
        """将受信 Conversation 映射到 PydanticAI 原生 History。"""

        if (
            not runtime_input.conversation
            or runtime_input.conversation[-1].role is not LLMRole.USER
        ):
            raise ValueError("Conversation 必须以当前 User Message 结束")
        history: list[ModelMessage] = []
        for message in runtime_input.conversation[:-1]:
            if message.content is None:
                raise ValueError("History 不接受空文本或历史 Tool Message")
            if message.role is LLMRole.USER:
                history.append(ModelRequest(parts=(UserPromptPart(message.content),)))
            elif message.role is LLMRole.ASSISTANT:
                history.append(ModelResponse(parts=(TextPart(message.content),)))
            else:
                raise ValueError("Spike History 只接受 User / Assistant")
        user_prompt = runtime_input.conversation[-1].content
        if user_prompt is None:
            raise ValueError("当前 User Message 不能为空")
        return history, user_prompt

    def _toolset(
        self,
        definitions: tuple[LLMToolDefinition, ...],
        bridge: _ToolBridge,
    ) -> FunctionToolset[None] | None:
        """用三个代表性 Tool 的公开函数签名建立薄 Bridge。"""

        if not definitions:
            return None
        toolset: FunctionToolset[None] = FunctionToolset(id="position-pilot-phase3")
        for definition in definitions:
            if definition.name == "get_current_quote":

                def get_current_quote(ticker: str) -> str:
                    """读取当前报价。"""

                    return bridge.execute("get_current_quote", {"ticker": ticker})

                toolset.add_function(
                    get_current_quote,
                    name=definition.name,
                    description=definition.description,
                )
            elif definition.name == SEARCH_TOOL_NAME:

                def search_web(query: str) -> str:
                    """搜索公开网页。"""

                    return bridge.execute(SEARCH_TOOL_NAME, {"query": query})

                toolset.add_function(
                    search_web,
                    name=definition.name,
                    description=definition.description,
                )
            elif definition.name == FETCH_TOOL_NAME:

                def fetch_page(url: str) -> str:
                    """读取公开网页。"""

                    return bridge.execute(FETCH_TOOL_NAME, {"url": url})

                toolset.add_function(
                    fetch_page,
                    name=definition.name,
                    description=definition.description,
                )
            else:
                raise ValueError(f"Pydantic Bridge 暂不支持 Tool: {definition.name}")
        return toolset

    def _latency_ms(self, started_at: float) -> float:
        """记录框架候选总耗时。"""

        return max(0.0, (self._clock() - started_at) * 1000)

    def _failure(
        self,
        failure: str,
        started_at: float,
        *,
        bridge: _ToolBridge | None = None,
        failure_detail: str | None = None,
    ) -> RuntimeResult:
        """候选失败不生成伪造 Answer，也不泄露异常正文。"""

        detail = failure if failure_detail is None else f"{failure}:{failure_detail}"
        return RuntimeResult(
            RuntimeExecutionStatus.CANDIDATE_FAILURE,
            None,
            detail,
            () if bridge is None else tuple(bridge.sources.values()),
            (),
            () if bridge is None else tuple(bridge.trace),
            None,
            self._latency_ms(started_at),
            () if bridge is None else tuple(bridge.warnings),
        )
