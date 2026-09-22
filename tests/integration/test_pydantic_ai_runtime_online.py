"""当前 Production Model / Provider 的 PydanticAI 最小在线证据。"""

import json
import os
from collections.abc import Callable, Mapping

import pytest
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolBinding,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMRole,
    LLMToolDefinition,
)
from position_pilot.application.tool_catalog import ToolExecutionResult
from position_pilot.config import Settings
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime

pytestmark = [pytest.mark.integration, pytest.mark.online]


def _runtime_settings() -> Settings:
    """只从当前 Process Environment 构造配置，不加载 Repository .env。"""

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    if not api_key or not base_url or not model:
        pytest.skip("需要 LLM_API_KEY、LLM_BASE_URL 与 LLM_MODEL")
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn(
            "postgresql+psycopg://runtime_smoke:unused@localhost/runtime_smoke"
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "ALIYUN_MODEL_STUDIO"),
        llm_api_key=SecretStr(api_key),
        llm_base_url=AnyHttpUrl(base_url),
        llm_model=model,
        llm_request_timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")),
    )


def _definition(name: str, description: str) -> LLMToolDefinition:
    return LLMToolDefinition(
        name,
        description,
        {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    )


def _request(
    question: str,
    tools: tuple[AgentToolBinding, ...] = (),
) -> AgentRunRequest:
    return AgentRunRequest(
        (
            LLMMessage(
                LLMRole.SYSTEM,
                "严格按用户要求调用指定工具；完成后只返回简短 JSON object。",
            ),
            LLMMessage(LLMRole.USER, question),
        ),
        tools,
        AgentRunBudget(model_requests=4, tool_calls=4, wall_clock_seconds=45),
        LLMResponseFormat.JSON_OBJECT,
    )


def _fixture_executor(
    label: str,
) -> Callable[[Mapping[str, object]], ToolExecutionResult]:
    def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
        return ToolExecutionResult(
            "OK",
            {"label": label, "ticker": arguments.get("ticker")},
            sources=({"source_id": f"fixture-{label}", "provider": "LOCAL_FIXTURE"},),
        )

    return execute


def _print_evidence(name: str, result: AgentRunResult, settings: Settings) -> None:
    """只输出不含 Credential / Endpoint 的可复核运行摘要。"""

    payload = {
        "scenario": name,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "status": result.status.value,
        "latency_ms": result.latency_ms,
        "usage_measured": result.usage is not None,
        "tool_names": [trace.name for trace in result.tool_trace],
        "tool_arguments": [dict(trace.arguments) for trace in result.tool_trace],
        "warnings": list(result.warnings),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


@pytest.mark.parametrize("scenario", ("no_tool", "one_tool", "multi_tool"))
def test_current_production_model_native_tool_compatibility(scenario: str) -> None:
    """显式启用时验证实际 Model 的 No / One / Multi-tool Native Loop。"""

    if os.getenv("RUN_PYDANTICAI_PRODUCTION_SMOKE") != "1":
        pytest.skip("需要显式启用 PydanticAI Production Smoke")
    settings = _runtime_settings()
    runtime = create_pydantic_ai_runtime(settings)
    quote = AgentToolBinding(
        _definition("get_fixture_quote", "必须调用一次以读取 GOOG 固定报价。"),
        _fixture_executor("quote"),
    )
    context = AgentToolBinding(
        _definition("get_fixture_market_context", "必须调用一次以读取固定市场状态。"),
        _fixture_executor("market-context"),
    )
    if scenario == "no_tool":
        request = _request('直接返回 {"answer":"NO_TOOL_OK"}，不得调用工具。')
        expected_tools: set[str] = set()
    elif scenario == "one_tool":
        request = _request(
            "调用 get_fixture_quote，ticker 必须为 GOOG，然后返回 JSON。",
            (quote,),
        )
        expected_tools = {"get_fixture_quote"}
    else:
        request = _request(
            "依次调用 get_fixture_quote 和 get_fixture_market_context，"
            "两次 ticker 都必须为 GOOG，然后返回 JSON。",
            (quote, context),
        )
        expected_tools = {"get_fixture_quote", "get_fixture_market_context"}

    result = runtime.run(request)
    _print_evidence(scenario, result, settings)

    assert result.status is AgentRunStatus.COMPLETED
    assert {trace.name for trace in result.tool_trace} == expected_tools
    assert all(trace.arguments == {"ticker": "GOOG"} for trace in result.tool_trace)
