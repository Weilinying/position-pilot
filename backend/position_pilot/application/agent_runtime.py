"""Production Agent Framework 的 Application-owned Port。"""

from typing import Protocol

from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMResult,
    LLMToolDefinition,
)


class AgentRuntime(Protocol):
    """执行一次 Provider-neutral 模型调用的最小 Runtime Port。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult: ...
