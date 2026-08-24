"""Provider-neutral LLM Contract 测试。"""

import pytest

from position_pilot.application.llm import (
    LLMMessage,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
)


def test_assistant_tool_call_uses_provider_neutral_schema() -> None:
    """Application Schema 只表达通用 Tool Call，不包含 Provider 类型。"""

    message = LLMMessage(
        LLMRole.ASSISTANT,
        None,
        (LLMToolCall("call-1", "get_current_quote", {"ticker": "GOOG"}),),
    )

    result = LLMResult.success(message)

    assert result.status is LLMStatus.OK
    assert result.completion is not None
    assert result.completion.message.tool_calls[0].arguments == {"ticker": "GOOG"}


def test_tool_message_requires_matching_call_id() -> None:
    """Tool Result 必须能关联原始 Tool Call。"""

    with pytest.raises(ValueError, match="tool_call_id"):
        LLMMessage(LLMRole.TOOL, '{"status":"OK"}')


def test_llm_failure_cannot_contain_completion() -> None:
    """LLM Provider Failure 不得伪装为可用 Completion。"""

    with pytest.raises(ValueError, match="不能包含 completion"):
        LLMResult(
            LLMStatus.PROVIDER_UNAVAILABLE,
            LLMResult.success(LLMMessage(LLMRole.ASSISTANT, "answer")).completion,
            "不可用",
        )
