"""Gemini 官方 Final 装配；复用当前 Phase 4B Runtime，不启用 Search。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from google.genai import Client
from google.genai.types import HttpOptions, HttpRetryOptions
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from position_pilot.config import Settings
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime

GOOGLE_API_BASE_URL = "https://generativelanguage.googleapis.com"


def create_gemini_runtime(settings: Settings) -> PydanticAIRuntime:
    """使用独立 Gemini Key 与 NativeOutput，不回退到其他 Provider 或兼容端点。"""

    api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    timeout = settings.native_llm_request_timeout_seconds
    if not api_key or not api_key.strip():
        return PydanticAIRuntime(
            None,
            provider_name=settings.llm_provider,
            model_name=settings.llm_model,
            timeout_seconds=timeout,
            max_retries=0,
            output_mechanism="NATIVE",
        )

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        # 每轮连接的创建、使用与关闭必须在同一个 Event Loop 内完成。
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as http_client:
            client = Client(
                vertexai=False,
                api_key=api_key,
                http_options=HttpOptions(
                    base_url=GOOGLE_API_BASE_URL,
                    timeout=int(timeout * 1000),
                    retry_options=HttpRetryOptions(attempts=1),
                    httpx_async_client=http_client,
                ),
            )
            try:
                yield GoogleModel(settings.llm_model, provider=GoogleProvider(client=client))
            finally:
                await client.aio.aclose()
                client.close()

    return PydanticAIRuntime(
        None,
        provider_name=settings.llm_provider,
        model_name=settings.llm_model,
        timeout_seconds=timeout,
        max_retries=0,
        model_context_factory=model_context,
        output_mechanism="NATIVE",
    )
