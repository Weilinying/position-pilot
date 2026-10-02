"""仅用于 Phase 4 Eval 的客户端装配与保守错误归因。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from time import monotonic

from openai import AsyncOpenAI
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers import Provider
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


class GeminiEvalRuntime(PydanticAIRuntime):
    """只为 Phase 4 Artifact 保存不含 Prompt、Tool 参数或回答正文的模型轮次。"""

    phase4_request_trace: list[dict[str, object]]


class _GeminiRequestTraceModel(WrapperModel):
    """记录每次模型返回的工具名称，区分分步调用与同轮批量调用。"""

    def __init__(self, wrapped: Model, trace: list[dict[str, object]]) -> None:
        super().__init__(wrapped)
        self.trace = trace

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        latest = messages[-1] if messages else None
        parts = latest.parts if isinstance(latest, ModelRequest) else ()
        entry: dict[str, object] = {
            "request_index": len(self.trace) + 1,
            "tool_results_in_latest_request": [
                part.tool_name for part in parts if isinstance(part, ToolReturnPart)
            ],
            "framework_retry_in_latest_request": any(
                isinstance(part, RetryPromptPart) for part in parts
            ),
        }
        started = monotonic()
        try:
            response = await self.wrapped.request(
                messages, model_settings, model_request_parameters
            )
        except BaseException as error:
            entry.update(
                status="ERROR",
                error_type=type(error).__name__,
                latency_ms=round((monotonic() - started) * 1000, 2),
            )
            self.trace.append(entry)
            raise
        entry.update(
            status="COMPLETED",
            latency_ms=round((monotonic() - started) * 1000, 2),
            response_part_types=[type(part).__name__ for part in response.parts],
            tool_call_names=[
                part.tool_name for part in response.parts if isinstance(part, ToolCallPart)
            ],
        )
        self.trace.append(entry)
        return response


def probe_provider(client: AsyncOpenAI, provider_name: str) -> Provider[AsyncOpenAI]:
    """只支持当前两个实验入口，避免给其他服务套用 Alibaba Profile。"""

    if provider_name == "ALIYUN_MODEL_STUDIO":
        return AlibabaProvider(openai_client=client)
    if provider_name == "AIHUBMIX":
        return OpenAIProvider(openai_client=client)
    raise ValueError(f"未接入的实验 Provider: {provider_name}")


def native_profile(provider: Provider[AsyncOpenAI], model: str) -> OpenAIModelProfile:
    """局部开启 Schema 请求以实测能力，不修改全局或生产 Profile。"""

    return replace(
        OpenAIModelProfile.from_profile(provider.model_profile(model)),
        supports_json_schema_output=True,
    )


def aihubmix_runtime(*, api_key: str, base_url: str, model_name: str) -> PydanticAIRuntime:
    """在测试装配边界复用现有 Native Runtime，默认生产配置不受影响。"""

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        async with AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=30.0, max_retries=0
        ) as client:
            provider = probe_provider(client, "AIHUBMIX")
            yield OpenAIChatModel(
                model_name, provider=provider, profile=native_profile(provider, model_name)
            )

    return PydanticAIRuntime(
        None,
        provider_name="AIHUBMIX",
        model_name=model_name,
        timeout_seconds=30.0,
        max_retries=0,
        model_context_factory=model_context,
        output_mechanism="NATIVE",
    )


def gemini_runtime(*, api_key: str, model_name: str) -> PydanticAIRuntime:
    """仅为 Phase 4 Core Fixture 装配 Gemini 官方原生 Native Runtime。"""

    if model_name != "gemini-3.8-flash":
        raise ValueError("本轮 Gemini Core 只允许 gemini-3.8-flash")
    trace: list[dict[str, object]] = []

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        import httpx
        from google.genai import Client
        from google.genai.types import HttpOptions, HttpRetryOptions
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as http_client:
            client = Client(
                vertexai=False,
                api_key=api_key,
                http_options=HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    timeout=30_000,
                    retry_options=HttpRetryOptions(attempts=1),
                    httpx_async_client=http_client,
                ),
            )
            try:
                yield _GeminiRequestTraceModel(
                    GoogleModel(model_name, provider=GoogleProvider(client=client)), trace
                )
            finally:
                await client.aio.aclose()
                client.close()

    runtime = GeminiEvalRuntime(
        None,
        provider_name="GOOGLE_GEMINI",
        model_name=model_name,
        timeout_seconds=30.0,
        max_retries=0,
        model_context_factory=model_context,
        output_mechanism="NATIVE",
    )
    runtime.phase4_request_trace = trace
    return runtime


def classify_failure(
    *,
    status: object = None,
    message: str = "",
    code: str = "",
) -> tuple[str, str]:
    """只对明确证据归因；普通 Schema/解析失败不自动归咎 Provider 或 Agent。"""

    if status in (401, 403):
        return "ACCESS_OR_AUTH", code or f"HTTP_{status}"
    if status == 429:
        return "RATE_LIMIT", code or "HTTP_429"
    if code in {"MODEL_REQUEST_BUDGET_EXCEEDED", "TOOL_CALL_BUDGET_EXCEEDED"}:
        return "RUNTIME_BUDGET", code
    if code == "MODEL_TIMEOUT_OR_TRANSPORT_FAILURE":
        return "UNCLASSIFIED", code
    if "TIMEOUT" in code.upper() or "WALL_CLOCK" in code.upper():
        return "TIMEOUT", code
    if isinstance(status, int) and status >= 500:
        return "PROVIDER_UNAVAILABLE", code or f"HTTP_{status}"
    lower = message.lower()
    if (
        status == 400
        and any(item in lower for item in ("response_format", "tool_choice", "json_schema"))
        and any(item in lower for item in ("not support", "unsupported", "unavailable"))
    ):
        return "PROVIDER_CAPABILITY", code or "OUTPUT_MECHANISM_REJECTED"
    if code in {"INVALID_AGENT_REQUEST", "UserError", "ValueError", "TypeError"}:
        return "HARNESS_OR_INTEGRATION", code
    return "UNCLASSIFIED", code or (f"HTTP_{status}" if status else "UNKNOWN_FAILURE")
