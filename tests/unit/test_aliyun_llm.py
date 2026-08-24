"""阿里云 Model Studio LLM Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from position_pilot.application.llm import (
    LLMMessage,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
)
from position_pilot.integrations.aliyun_llm import (
    AliyunLLMProvider,
    LLMJsonHttpResponse,
    LLMTransportFailureKind,
    LLMTransportUnavailable,
)


@dataclass(frozen=True, slots=True)
class RecordedLLMRequest:
    url: str
    headers: dict[str, str]
    payload: dict[str, object]
    timeout_seconds: float


@dataclass(slots=True)
class FakeLLMTransport:
    """返回固定 JSON 并记录 OpenAI-compatible 请求。"""

    responses: list[LLMJsonHttpResponse]
    requests: list[RecordedLLMRequest] = field(default_factory=list)

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> LLMJsonHttpResponse:
        self.requests.append(
            RecordedLLMRequest(url, dict(headers), dict(payload), timeout_seconds)
        )
        return self.responses.pop(0)


class UnavailableLLMTransport:
    """模拟不泄露底层异常或 Secret 的网络失败。"""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> LLMJsonHttpResponse:
        try:
            raise RuntimeError("test-secret must not leak")
        except RuntimeError as error:
            raise LLMTransportUnavailable(LLMTransportFailureKind.NETWORK_ERROR) from error


def make_provider(
    transport: FakeLLMTransport | UnavailableLLMTransport,
    *,
    api_key: str | None = "test-secret",
) -> AliyunLLMProvider:
    """创建不访问网络的固定 Adapter。"""

    return AliyunLLMProvider(
        api_key=api_key,
        base_url="https://llm.example.test/compatible-mode/v1",
        model="configured-model",
        timeout_seconds=7,
        transport=transport,
    )


def current_quote_tool() -> LLMToolDefinition:
    """返回测试用通用 Tool Definition。"""

    return LLMToolDefinition(
        "get_current_quote",
        "获取当前行情",
        {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    )


def test_serializes_generic_messages_tools_and_configured_model() -> None:
    """Adapter 负责转换 OpenAI-compatible Payload，不把格式泄露给 Application。"""

    transport = FakeLLMTransport(
        [
            LLMJsonHttpResponse(
                200,
                {
                    "choices": [
                        {"message": {"role": "assistant", "content": "无需行情即可回答"}}
                    ]
                },
            )
        ]
    )

    result = make_provider(transport).complete(
        (
            LLMMessage(LLMRole.SYSTEM, "system"),
            LLMMessage(LLMRole.USER, "question"),
        ),
        tools=(current_quote_tool(),),
    )

    assert result.status is LLMStatus.OK
    request = transport.requests[0]
    assert request.url.endswith("/compatible-mode/v1/chat/completions")
    assert request.payload["model"] == "configured-model"
    assert request.payload["enable_thinking"] is False
    assert request.payload["parallel_tool_calls"] is True
    assert request.headers["Authorization"] == "Bearer test-secret"
    assert "get_current_quote" in str(request.payload["tools"])


def test_parses_multiple_function_calls_into_generic_schema() -> None:
    """一个 Provider Response 可以携带多个通用 Tool Call。"""

    transport = FakeLLMTransport(
        [
            LLMJsonHttpResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_current_quote",
                                            "arguments": '{"ticker":"GOOG"}',
                                        },
                                    },
                                    {
                                        "id": "call-2",
                                        "type": "function",
                                        "function": {
                                            "name": "get_current_quote",
                                            "arguments": '{"ticker":"MSFT"}',
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                },
            )
        ]
    )

    result = make_provider(transport).complete(
        (LLMMessage(LLMRole.USER, "比较 GOOG 和 MSFT"),),
        tools=(current_quote_tool(),),
    )

    assert result.completion is not None
    assert [
        call.arguments["ticker"] for call in result.completion.message.tool_calls
    ] == ["GOOG", "MSFT"]


def test_serializes_assistant_tool_call_and_tool_result_for_final_completion() -> None:
    """第二次 Completion 应保留 Tool Call 与对应 Result 的通用关联。"""

    transport = FakeLLMTransport(
        [
            LLMJsonHttpResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "final"}}]},
            )
        ]
    )
    assistant = LLMMessage(
        LLMRole.ASSISTANT,
        None,
        (LLMToolCall("call-1", "get_current_quote", {"ticker": "GOOG"}),),
    )
    tool_result = LLMMessage(
        LLMRole.TOOL,
        '{"status":"OK","ticker":"GOOG"}',
        tool_call_id="call-1",
    )

    make_provider(transport).complete((assistant, tool_result))

    serialized_messages = transport.requests[0].payload["messages"]
    assert isinstance(serialized_messages, list)
    assert serialized_messages[0]["tool_calls"][0]["function"]["arguments"] == (
        '{"ticker": "GOOG"}'
    )
    assert serialized_messages[1]["tool_call_id"] == "call-1"
    assert "tools" not in transport.requests[0].payload


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, LLMStatus.INVALID_REQUEST),
        (401, LLMStatus.AUTHENTICATION_FAILED),
        (429, LLMStatus.RATE_LIMITED),
        (503, LLMStatus.PROVIDER_UNAVAILABLE),
    ],
)
def test_maps_http_failure_without_exposing_provider_payload(
    status_code: int,
    expected: LLMStatus,
) -> None:
    """Provider HTTP Error 必须映射为稳定且安全的 LLM Failure。"""

    transport = FakeLLMTransport(
        [LLMJsonHttpResponse(status_code, {"message": "test-secret leaked by upstream"})]
    )

    result = make_provider(transport).complete((LLMMessage(LLMRole.USER, "question"),))

    assert result.status is expected
    assert result.error_message is not None
    assert "test-secret" not in result.error_message


def test_missing_credential_fails_before_transport_call() -> None:
    """缺少 Credential 时不得发出包含 Portfolio Context 的网络请求。"""

    transport = FakeLLMTransport([])

    result = make_provider(transport, api_key=None).complete(
        (LLMMessage(LLMRole.USER, "question"),)
    )

    assert result.status is LLMStatus.AUTHENTICATION_FAILED
    assert transport.requests == []


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"choices": []},
        {"choices": [{"message": {"role": "assistant", "content": 123}}]},
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "get_current_quote",
                                    "arguments": "not-json",
                                },
                            }
                        ],
                    }
                }
            ]
        },
    ],
)
def test_rejects_invalid_provider_response(payload: object) -> None:
    """不完整或非法 Provider Payload 不得成为 Completion。"""

    result = make_provider(FakeLLMTransport([LLMJsonHttpResponse(200, payload)])).complete(
        (LLMMessage(LLMRole.USER, "question"),)
    )

    assert result.status is LLMStatus.INVALID_PROVIDER_RESPONSE
    assert result.completion is None


def test_transport_failure_does_not_leak_chained_exception() -> None:
    """网络失败只返回稳定类别，不暴露底层异常内容。"""

    result = make_provider(UnavailableLLMTransport()).complete(
        (LLMMessage(LLMRole.USER, "question"),)
    )

    assert result.status is LLMStatus.PROVIDER_UNAVAILABLE
    assert result.error_message == "LLM Provider 网络连接失败"
