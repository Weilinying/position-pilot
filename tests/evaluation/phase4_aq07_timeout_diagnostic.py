"""AQ07 专用在线耗时诊断；不改变 4A Primary 或 Production 预算。"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import monotonic
from typing import cast

from ask_quality_cases import CASES_BY_ID
from openai import AsyncOpenAI
from phase4_core_harness import RecordingAgentRuntime, execute_native_case
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.settings import ModelSettings

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRuntime,
    AgentToolBinding,
)
from position_pilot.application.tool_catalog import ToolExecutionResult
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


@dataclass(slots=True)
class DiagnosticTrace:
    """只记录阶段、耗时及状态，不记录 Prompt、Tool 参数或凭据。"""

    started_at: float = field(default_factory=monotonic)
    phase: str = "INITIAL"
    events: list[dict[str, object]] = field(default_factory=list)

    def mark(self, kind: str, started_at: float, **details: object) -> None:
        """记录相对开始时间，保留 Model / Tool 的真实先后顺序。"""

        self.events.append(
            {
                "kind": kind,
                "phase": self.phase,
                "started_ms": round((started_at - self.started_at) * 1000, 2),
                "duration_ms": round((monotonic() - started_at) * 1000, 2),
                **details,
            }
        )


class TimedModel(WrapperModel):
    """仅在 Eval 中观察每次 Provider 请求与 Final Output Tool。"""

    def __init__(self, wrapped: Model, trace: DiagnosticTrace) -> None:
        super().__init__(wrapped)
        self._trace = trace

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """超时取消也记录，避免把无 Final Candidate 误判为格式错误。"""

        started_at = monotonic()
        try:
            result = await self.wrapped.request(messages, model_settings, model_request_parameters)
        except asyncio.CancelledError:
            self._trace.mark("MODEL_REQUEST", started_at, status="CANCELLED_BY_BUDGET")
            raise
        except Exception as error:
            self._trace.mark(
                "MODEL_REQUEST", started_at, status="ERROR", error_type=type(error).__name__
            )
            raise
        tool_names = [part.tool_name for part in result.parts if isinstance(part, ToolCallPart)]
        usage = result.usage
        self._trace.mark(
            "MODEL_REQUEST",
            started_at,
            status="COMPLETED",
            tool_names=tool_names,
            final_output_tool_called="final_investment_answer" in tool_names,
            usage=(
                "UNKNOWN"
                if usage.input_tokens == 0 and usage.output_tokens == 0
                else {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                }
            ),
        )
        return result


@dataclass(slots=True)
class TimedToolRuntime:
    """只包裹 Eval Tool Executor；原始结果与安全校验均不变。"""

    delegate: AgentRuntime
    trace: DiagnosticTrace
    run_count: int = 0

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """记录一次 Tool 执行，不记录可能含敏感信息的入参。"""

        self.run_count += 1
        self.trace.phase = "INITIAL" if self.run_count == 1 else "REPAIR"

        def binding_with_timing(binding: AgentToolBinding) -> AgentToolBinding:
            def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
                started_at = monotonic()
                try:
                    result = binding.executor(arguments)
                except Exception as error:
                    self.trace.mark(
                        "TOOL",
                        started_at,
                        name=binding.definition.name,
                        status="ERROR",
                        error_type=type(error).__name__,
                    )
                    raise
                self.trace.mark(
                    "TOOL",
                    started_at,
                    name=binding.definition.name,
                    status=result.status,
                    related_tool_names=[item.name for item in result.related_calls],
                    timing_scope="INCLUDES_RELATED_CALLS",
                )
                return result

            return AgentToolBinding(binding.definition, execute)

        timed_request = replace(
            request, tools=tuple(binding_with_timing(item) for item in request.tools)
        )
        return self.delegate.run(timed_request)


def run_aq07_timeout_diagnostic(
    *,
    api_key: str,
    base_url: str,
    model_name: str,
    timeout_seconds: int,
    artifact_dir: Path,
) -> dict[str, object]:
    """用固定 AQ07 Fixture 运行单次 30/60 秒 Eval，不写入 Primary 证据。"""

    if timeout_seconds not in {30, 60}:
        raise ValueError("AQ07 诊断只允许 30 或 60 秒")
    if not api_key or not base_url or not model_name:
        raise ValueError("AQ07 诊断缺少模型配置")
    artifact_dir.mkdir(parents=True, exist_ok=False)
    trace = DiagnosticTrace()

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds, max_retries=0
        )
        try:
            model = OpenAIChatModel(model_name, provider=AlibabaProvider(openai_client=client))
            yield TimedModel(model, trace)
        finally:
            await client.close()

    native_runtime = PydanticAIRuntime(
        None,
        provider_name="ALIYUN_MODEL_STUDIO",
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        max_retries=0,
        model_context_factory=model_context,
    )
    runtime = RecordingAgentRuntime(TimedToolRuntime(native_runtime, trace))
    record = execute_native_case(
        CASES_BY_ID["AQ07"], runtime, wall_clock_budget_seconds=timeout_seconds
    )
    turn = cast(list[dict[str, object]], record["turns"])[0]
    case_summary = {
        "execution_status": record["execution_status"],
        "failure_code": turn.get("failure_code"),
        "response_status": turn.get("response_status"),
        "answer": turn.get("answer"),
        "latency_ms": turn["latency_ms"],
        "repair_count": turn["repair_count"],
        "tool_names": [item["name"] for item in cast(list[dict[str, object]], turn["tool_trace"])],
        "usage": turn["usage"],
    }
    artifact = {
        "kind": "AQ07_EVAL_ONLY_TIMEOUT_DIAGNOSTIC",
        "production_budget_changed": False,
        "timeout_seconds": timeout_seconds,
        "model": model_name,
        "events": sorted(trace.events, key=lambda item: cast(float, item["started_ms"])),
        "case": case_summary,
    }
    (artifact_dir / "diagnostic.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact
