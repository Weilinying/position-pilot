"""Provider-neutral LLM Contract。"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class LLMRole(StrEnum):
    """Application 允许使用的通用消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMStatus(StrEnum):
    """与具体 Provider 无关的 LLM 调用结果。"""

    OK = "OK"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"


class LLMResponseFormat(StrEnum):
    """Provider-neutral Completion 输出格式约束。"""

    TEXT = "TEXT"
    JSON_OBJECT = "JSON_OBJECT"


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    """模型请求 Application 执行的通用 Tool Call。"""

    id: str
    name: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Tool Call id 不能为空")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool Call name 不能为空")
        if not isinstance(self.arguments, Mapping):
            raise ValueError("Tool Call arguments 必须是 object")


@dataclass(frozen=True, slots=True)
class LLMToolDefinition:
    """向模型暴露的通用 Function Tool 定义。"""

    name: str
    description: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool name 不能为空")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Tool description 不能为空")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("Tool parameters 必须是 JSON Schema object")


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Application 内部使用的通用 LLM Message。"""

    role: LLMRole
    content: str | None
    tool_calls: tuple[LLMToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, LLMRole):
            raise ValueError("LLM Message role 无效")
        if self.content is not None and (
            not isinstance(self.content, str) or not self.content.strip()
        ):
            raise ValueError("LLM Message content 必须是非空字符串或 None")
        if not isinstance(self.tool_calls, tuple) or any(
            not isinstance(tool_call, LLMToolCall) for tool_call in self.tool_calls
        ):
            raise ValueError("tool_calls 必须是 LLMToolCall tuple")

        if self.role is LLMRole.ASSISTANT:
            if self.content is None and not self.tool_calls:
                raise ValueError("Assistant Message 必须包含 content 或 tool_calls")
            if self.tool_call_id is not None:
                raise ValueError("Assistant Message 不能包含 tool_call_id")
            return

        if self.tool_calls:
            raise ValueError("只有 Assistant Message 可以包含 tool_calls")
        if self.role is LLMRole.TOOL:
            if self.content is None:
                raise ValueError("Tool Message 必须包含 content")
            if not isinstance(self.tool_call_id, str) or not self.tool_call_id.strip():
                raise ValueError("Tool Message 必须包含 tool_call_id")
            return
        if self.content is None:
            raise ValueError("System/User Message 必须包含 content")
        if self.tool_call_id is not None:
            raise ValueError("非 Tool Message 不能包含 tool_call_id")


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    """一次成功 Completion 的 Provider-neutral 输出。"""

    message: LLMMessage

    def __post_init__(self) -> None:
        if self.message.role is not LLMRole.ASSISTANT:
            raise ValueError("Completion 必须包含 Assistant Message")


@dataclass(frozen=True, slots=True)
class LLMResult:
    """明确区分成功 Completion 与 LLM Provider Failure。"""

    status: LLMStatus
    completion: LLMCompletion | None
    error_message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, LLMStatus):
            raise ValueError("LLM Result status 无效")
        if self.status is LLMStatus.OK:
            if self.completion is None or self.error_message is not None:
                raise ValueError("OK Result 必须只包含 completion")
            return
        if self.completion is not None:
            raise ValueError("Failure Result 不能包含 completion")
        if not isinstance(self.error_message, str) or not self.error_message.strip():
            raise ValueError("Failure Result 必须包含安全错误消息")

    @classmethod
    def success(cls, message: LLMMessage) -> "LLMResult":
        """创建成功结果。"""

        return cls(LLMStatus.OK, LLMCompletion(message), None)

    @classmethod
    def failure(cls, status: LLMStatus, message: str) -> "LLMResult":
        """创建不携带伪造 Completion 的失败结果。"""

        if status is LLMStatus.OK:
            raise ValueError("failure 不能使用 OK status")
        return cls(status, None, message)


class LLMProvider(Protocol):
    """Investment Agent 所依赖的最小 LLM Provider 接口。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult: ...
