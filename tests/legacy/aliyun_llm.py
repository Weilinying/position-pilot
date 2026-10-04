"""阿里云 Model Studio OpenAI-compatible LLM Adapter。"""

import json
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from http.client import HTTPResponse
from time import monotonic
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponseFormat,
    LLMResponseMetadata,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
    LLMUsage,
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


ALIYUN_MODEL_STUDIO = "ALIYUN_MODEL_STUDIO"


class OpenAICompatibleLLMProvider(LLMProvider):
    """将 OpenAI-compatible Chat Completions 转换为通用 LLM Result。"""

    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = True,
        transport: LLMJsonHttpTransport | None = None,
    ) -> None:
        self._provider_name = provider_name.strip().upper()
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._enable_thinking = enable_thinking
        self._parallel_tool_calls = parallel_tool_calls
        self._transport = transport or UrllibLLMJsonHttpTransport()

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """执行一次非流式 Completion，并隐藏 Provider Payload。"""

        started_at = monotonic()
        if not self._api_key:
            return LLMResult.failure(
                LLMStatus.AUTHENTICATION_FAILED,
                "LLM API credential 未配置",
                self._metadata(None, started_at),
            )
        if not messages:
            return LLMResult.failure(
                LLMStatus.INVALID_REQUEST,
                "LLM messages 不能为空",
                self._metadata(None, started_at),
            )

        payload: dict[str, object] = {
            "model": self._model,
            "messages": [self._serialize_message(message) for message in messages],
        }
        if self._enable_thinking is not None:
            payload["enable_thinking"] = self._enable_thinking
        if tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in tools]
            if self._parallel_tool_calls is not None:
                payload["parallel_tool_calls"] = self._parallel_tool_calls
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
                self._metadata(None, started_at),
            )
        failure = self._response_failure(response)
        if failure is not None:
            return LLMResult.failure(
                *failure,
                self._metadata(response.payload, started_at),
            )
        try:
            message = self._parse_completion_message(response.payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return LLMResult.failure(
                LLMStatus.INVALID_PROVIDER_RESPONSE,
                "LLM Provider response 格式无效",
                self._metadata(response.payload, started_at),
            )
        return LLMResult.success(message, self._metadata(response.payload, started_at))

    def _metadata(self, payload: object, started_at: float) -> LLMResponseMetadata:
        """从兼容响应提取通用可观测字段，不把原始 Payload 泄露给 Application。"""

        model = self._model
        response_id: str | None = None
        usage: LLMUsage | None = None
        if isinstance(payload, Mapping):
            raw_model = payload.get("model")
            if isinstance(raw_model, str) and raw_model.strip():
                model = raw_model.strip()
            raw_response_id = payload.get("id")
            if isinstance(raw_response_id, str) and raw_response_id.strip():
                response_id = raw_response_id.strip()
            usage = self._parse_usage(payload.get("usage"))
        return LLMResponseMetadata(
            provider=self._provider_name,
            model=model,
            latency_ms=round((monotonic() - started_at) * 1000, 2),
            usage=usage,
            response_id=response_id,
        )

    @staticmethod
    def _parse_usage(value: object) -> LLMUsage | None:
        """只接收完整的 OpenAI-compatible Token Usage；缺失时明确保持不可用。"""

        if not isinstance(value, Mapping):
            return None
        raw_values = (
            value.get("prompt_tokens"),
            value.get("completion_tokens"),
            value.get("total_tokens"),
        )
        if any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in raw_values
        ):
            return None
        input_tokens, output_tokens, total_tokens = cast(tuple[int, int, int], raw_values)
        return LLMUsage(input_tokens, output_tokens, total_tokens)

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
        if status_code == 408:
            return LLMStatus.PROVIDER_UNAVAILABLE, "LLM Provider 请求超时"
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


class AliyunLLMProvider(OpenAICompatibleLLMProvider):
    """隔离 Alibaba Model Studio 的 OpenAI-compatible 扩展参数。"""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: LLMJsonHttpTransport | None = None,
    ) -> None:
        super().__init__(
            provider_name=ALIYUN_MODEL_STUDIO,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            enable_thinking=False,
            parallel_tool_calls=True,
            transport=transport,
        )


def create_llm_provider(settings: Settings) -> OpenAICompatibleLLMProvider:
    """按配置创建薄 OpenAI-compatible Adapter。"""

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if settings.llm_provider == ALIYUN_MODEL_STUDIO:
        return AliyunLLMProvider(
            api_key=api_key,
            base_url=str(settings.llm_base_url),
            model=settings.llm_model,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )
    return OpenAICompatibleLLMProvider(
        provider_name=settings.llm_provider,
        api_key=api_key,
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        timeout_seconds=settings.llm_request_timeout_seconds,
    )
