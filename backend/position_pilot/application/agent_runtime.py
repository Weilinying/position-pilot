"""Production Agent Framework 的 Application-owned Port。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Protocol

from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMResult,
    LLMStatus,
    LLMToolDefinition,
    LLMUsage,
)
from position_pilot.application.tool_catalog import ToolExecutor


class AgentToolBudgetExceeded(RuntimeError):
    """Application Tool Session 在执行前拒绝超过本轮预算的调用。"""

    def __init__(self, tool_name: str | None = None) -> None:
        super().__init__("application tool quota exhausted")
        self.tool_name = tool_name


@dataclass(frozen=True, slots=True)
class AgentToolBinding:
    """将本轮 Framework Tool Definition 绑定到 Application Executor。"""

    definition: LLMToolDefinition
    executor: ToolExecutor


@dataclass(frozen=True, slots=True)
class AgentRunBudget:
    """单次 Run 预算；tool_calls 限制模型 attempt 准入，重复和拒绝也占额度。"""

    model_requests: int
    tool_calls: int
    wall_clock_seconds: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.model_requests, bool)
            or not isinstance(self.model_requests, int)
            or self.model_requests <= 0
        ):
            raise ValueError("model_requests 必须是正整数")
        if (
            isinstance(self.tool_calls, bool)
            or not isinstance(self.tool_calls, int)
            or self.tool_calls < 0
        ):
            raise ValueError("tool_calls 必须是非负整数")
        if (
            isinstance(self.wall_clock_seconds, bool)
            or not isinstance(self.wall_clock_seconds, (int, float))
            or not isfinite(self.wall_clock_seconds)
            or self.wall_clock_seconds <= 0
        ):
            raise ValueError("wall_clock_seconds 必须是正数")


@dataclass(frozen=True, slots=True)
class AgentToolTrace:
    """Application 可审计的单次 Tool 调用结果。"""

    name: str
    arguments: Mapping[str, object]
    status: str
    error_code: str | None = None
    sources: tuple[Mapping[str, object], ...] = ()
    invoked_by_model: bool = True
    provider_fetch_count: int = 1
    application_execution_count: int = 1
    cache_reused: bool = False
    duplicate_attempt: bool = False
    tool_call_id: str | None = None


class AgentRunStatus(StrEnum):
    """Native Agent Run 的稳定外层状态。"""

    COMPLETED = "COMPLETED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    """Application 提供给 Native Agent Runtime 的一次请求。"""

    messages: tuple[LLMMessage, ...]
    tools: tuple[AgentToolBinding, ...]
    budget: AgentRunBudget
    response_format: LLMResponseFormat = LLMResponseFormat.TEXT

    def __post_init__(self) -> None:
        names = tuple(binding.definition.name for binding in self.tools)
        if len(names) != len(set(names)):
            raise ValueError("Native Agent Tool name 不能重复")


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Native Agent Run 结果；Framework 不成为业务事实源。"""

    status: AgentRunStatus
    final_candidate: str | None
    failure_code: str | None
    tool_trace: tuple[AgentToolTrace, ...]
    sources: tuple[Mapping[str, object], ...]
    usage: LLMUsage | None
    latency_ms: float
    llm_status: LLMStatus | None = None
    warnings: tuple[str, ...] = ()
    provider_http_status: int | None = None
    provider_error_code: str | None = None
    provider_error_message: str | None = field(default=None, repr=False)
    framework_error_kind: str | None = None
    framework_error_cause: str | None = None
    provider_finish_reason: str | None = None
    model_request_count: int = 0
    tool_attempt_count: int = 0
    tool_attempt_admission_count: int = 0
    final_only_request_count: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or not isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("latency_ms 必须是非负有限数")
        if self.status is AgentRunStatus.COMPLETED:
            if not isinstance(self.final_candidate, str) or not self.final_candidate.strip():
                raise ValueError("COMPLETED 必须包含 final_candidate")
            if self.failure_code is not None:
                raise ValueError("COMPLETED 不能包含 failure_code")
        elif self.final_candidate is not None:
            raise ValueError("失败 Run 不能包含 final_candidate")
        elif not isinstance(self.failure_code, str) or not self.failure_code.strip():
            raise ValueError("失败 Run 必须包含稳定 failure_code")


class ModelCompletionRuntime(Protocol):
    """Legacy InvestmentAgent 使用的低层 Completion Port。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult: ...


class AgentRuntime(Protocol):
    """Production Agent 使用的高层 Native Tool Loop Port。"""

    def run(self, request: AgentRunRequest) -> AgentRunResult: ...


__all__ = [
    "AgentRunBudget",
    "AgentRunRequest",
    "AgentRunResult",
    "AgentRunStatus",
    "AgentRuntime",
    "AgentToolBinding",
    "AgentToolBudgetExceeded",
    "AgentToolTrace",
    "ModelCompletionRuntime",
]
