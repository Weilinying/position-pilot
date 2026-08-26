"""阿里云 Model Studio OpenAI-compatible LLM Adapter。"""

import json
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from http.client import HTTPResponse
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponseFormat,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
)
from position_pilot.config import Settings


@dataclass(frozen=True, slots=True)
class LLMJsonHttpResponse:
    """LLM HTTP Transport 返回的最小 JSON 响应。"""

    status_code: int
    payload: object


class LLMTransportFailureKind(StrEnum):
    """不泄露 URL、Credential 或底层异常文本的 Transport 错误类别。"""

    TLS_CERTIFICATE_ERROR = "TLS_CERTIFICATE_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"


class LLMTransportUnavailable(RuntimeError):
    """携带安全类别的 LLM 网络失败。"""

    def __init__(self, kind: LLMTransportFailureKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


class LLMJsonHttpTransport(Protocol):
    """便于 Unit Test 替换的同步 JSON POST Contract。"""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> LLMJsonHttpResponse: ...


class UrllibLLMJsonHttpTransport:
    """只负责 HTTPS POST 与 JSON 解码的标准库 Transport。"""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> LLMJsonHttpResponse:
        request = Request(
            url,
            headers=dict(headers),
            data=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return LLMJsonHttpResponse(response.status, self._decode_json(response))
        except HTTPError as error:
            return LLMJsonHttpResponse(error.code, self._decode_json(error))
        except URLError as error:
            raise LLMTransportUnavailable(self._classify_failure(error.reason)) from error
        except (TimeoutError, OSError) as error:
            raise LLMTransportUnavailable(self._classify_failure(error)) from error

    @staticmethod
    def _decode_json(response: HTTPResponse | HTTPError) -> object:
        try:
            return json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _classify_failure(error: object) -> LLMTransportFailureKind:
        if isinstance(error, ssl.SSLCertVerificationError):
            return LLMTransportFailureKind.TLS_CERTIFICATE_ERROR
        if isinstance(error, TimeoutError):
            return LLMTransportFailureKind.TIMEOUT
        return LLMTransportFailureKind.NETWORK_ERROR


class AliyunLLMProvider(LLMProvider):
    """将阿里云 OpenAI-compatible 语义转换为通用 LLM Result。"""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: LLMJsonHttpTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibLLMJsonHttpTransport()

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """执行一次非流式 Completion，并隐藏 Provider Payload。"""

        if not self._api_key:
            return LLMResult.failure(
                LLMStatus.AUTHENTICATION_FAILED,
                "LLM API credential 未配置",
            )
        if not messages:
            return LLMResult.failure(LLMStatus.INVALID_REQUEST, "LLM messages 不能为空")

        payload: dict[str, object] = {
            "model": self._model,
            "messages": [self._serialize_message(message) for message in messages],
            # M3 优先控制 Latency 与 Token 成本，复杂推理可在后续 Evaluation 中再评估。
            "enable_thinking": False,
        }
        if tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in tools]
            payload["parallel_tool_calls"] = True
        if response_format is LLMResponseFormat.JSON_OBJECT:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = self._transport.post_json(
                f"{self._base_url}/chat/completions",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )
        except LLMTransportUnavailable as error:
            return LLMResult.failure(
                LLMStatus.PROVIDER_UNAVAILABLE,
                self._transport_failure_message(error.kind),
            )
        failure = self._response_failure(response)
        if failure is not None:
            return LLMResult.failure(*failure)
        try:
            message = self._parse_completion_message(response.payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return LLMResult.failure(
                LLMStatus.INVALID_PROVIDER_RESPONSE,
                "LLM Provider response 格式无效",
            )
        return LLMResult.success(message)

    @staticmethod
    def _serialize_message(message: LLMMessage) -> dict[str, object]:
        serialized: dict[str, object] = {"role": message.role.value}
        if message.content is not None:
            serialized["content"] = message.content
        else:
            serialized["content"] = None
        if message.tool_calls:
            serialized["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(dict(tool_call.arguments), ensure_ascii=False),
                    },
                }
                for tool_call in message.tool_calls
            ]
        if message.tool_call_id is not None:
            serialized["tool_call_id"] = message.tool_call_id
        return serialized

    @staticmethod
    def _serialize_tool(tool: LLMToolDefinition) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            },
        }

    @classmethod
    def _parse_completion_message(cls, payload: object) -> LLMMessage:
        if not isinstance(payload, Mapping):
            raise ValueError("payload 不是 JSON object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("choices 必须只包含一个结果")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise ValueError("choice 格式无效")
        raw_message = choice.get("message")
        if not isinstance(raw_message, Mapping):
            raise ValueError("message 格式无效")
        if raw_message.get("role") != "assistant":
            raise ValueError("message role 必须是 assistant")

        raw_content = raw_message.get("content")
        if raw_content is not None and not isinstance(raw_content, str):
            raise ValueError("message content 类型无效")
        content = raw_content if isinstance(raw_content, str) and raw_content.strip() else None
        raw_tool_calls = raw_message.get("tool_calls")
        tool_calls = cls._parse_tool_calls(raw_tool_calls)
        return LLMMessage(LLMRole.ASSISTANT, content, tool_calls)

    @staticmethod
    def _parse_tool_calls(value: object) -> tuple[LLMToolCall, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or not value:
            raise ValueError("tool_calls 格式无效")
        parsed: list[LLMToolCall] = []
        seen_ids: set[str] = set()
        for raw_call in value:
            if not isinstance(raw_call, Mapping) or raw_call.get("type") != "function":
                raise ValueError("tool_call 格式无效")
            call_id = raw_call.get("id")
            function = raw_call.get("function")
            if not isinstance(call_id, str) or not isinstance(function, Mapping):
                raise ValueError("tool_call id 或 function 无效")
            if call_id in seen_ids:
                raise ValueError("tool_call id 重复")
            name = function.get("name")
            raw_arguments = function.get("arguments")
            if not isinstance(name, str) or not isinstance(raw_arguments, str):
                raise ValueError("tool_call name 或 arguments 无效")
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, Mapping):
                raise ValueError("tool_call arguments 必须是 object")
            parsed.append(LLMToolCall(call_id, name, dict(arguments)))
            seen_ids.add(call_id)
        return tuple(parsed)

    @staticmethod
    def _response_failure(
        response: LLMJsonHttpResponse,
    ) -> tuple[LLMStatus, str] | None:
        status_code = response.status_code
        if 200 <= status_code < 300:
            return None
        if status_code in {400, 404, 422}:
            return LLMStatus.INVALID_REQUEST, "LLM Provider 拒绝了请求"
        if status_code in {401, 403}:
            return LLMStatus.AUTHENTICATION_FAILED, "LLM Provider credential 无效"
        if status_code == 429:
            return LLMStatus.RATE_LIMITED, "LLM Provider 请求达到限流"
        if status_code >= 500:
            return LLMStatus.PROVIDER_UNAVAILABLE, "LLM Provider 当前不可用"
        return LLMStatus.INVALID_PROVIDER_RESPONSE, "LLM Provider 返回未识别的 HTTP 状态"

    @staticmethod
    def _transport_failure_message(kind: LLMTransportFailureKind) -> str:
        if kind is LLMTransportFailureKind.TLS_CERTIFICATE_ERROR:
            return "LLM Provider TLS 证书校验失败"
        if kind is LLMTransportFailureKind.TIMEOUT:
            return "LLM Provider 请求超时"
        return "LLM Provider 网络连接失败"


def create_aliyun_llm_provider(settings: Settings) -> AliyunLLMProvider:
    """从通用 Settings 创建 Aliyun Adapter，不向 Application 暴露 Secret。"""

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return AliyunLLMProvider(
        api_key=api_key,
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        timeout_seconds=settings.llm_request_timeout_seconds,
    )
