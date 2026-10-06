"""Gemini 官方 Final Runtime 的离线接线测试。"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from google.genai import Client as SDKClient
from google.genai.types import HttpOptions
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunStatus,
    AgentToolBinding,
)
from position_pilot.application.investment_answer import parse_structured_answer
from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMRole,
    LLMToolDefinition,
)
from position_pilot.application.tool_catalog import ToolExecutionResult
from position_pilot.config import Settings
from position_pilot.domain.strategy import PositionPlanPayload
from position_pilot.integrations import gemini_runtime
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime


@pytest.fixture(autouse=True)
def deny_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """遗漏 Mock 时直接使离线测试失败，不能把网络错误当作预期结果。"""

    async def blocked(
        transport: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        pytest.fail("Gemini 离线测试禁止真实网络连接")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


def _settings(key: str | None = "offline-gemini-key") -> Settings:
    """创建不读取本地配置文件的 Gemini 设置。"""

    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn("postgresql+psycopg://unused:unused@localhost/unused"),
        llm_provider="GOOGLE_GEMINI",
        llm_model="gemini-3.8-flash",
        llm_base_url=AnyHttpUrl("https://unrelated-final.example/v1"),
        llm_api_key=SecretStr("unrelated-llm-key"),
        gemini_api_key=SecretStr(key) if key is not None else None,
    )


def _request(*, strategy_candidates_enabled: bool = False) -> AgentRunRequest:
    """创建包含报价工具的最小 JSON Final 请求。"""

    def quote(arguments: Mapping[str, object]) -> ToolExecutionResult:
        assert arguments == {"ticker": "GOOG"}
        return ToolExecutionResult("OK", {"price": "210"})

    binding = AgentToolBinding(
        LLMToolDefinition(
            "get_quote",
            "查询报价",
            {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
                "additionalProperties": False,
            },
        ),
        quote,
    )
    return AgentRunRequest(
        (
            LLMMessage(LLMRole.SYSTEM, "只根据可用事实作答。"),
            LLMMessage(LLMRole.USER, "请查询 GOOG 报价。"),
        ),
        (binding,),
        AgentRunBudget(2, 1, 60),
        LLMResponseFormat.JSON_OBJECT,
        strategy_candidates_enabled,
    )


def test_google_factory_runs_native_output_tool_loop_and_strategy_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google 原生 Schema、Function Tool Loop 与 4B 草案可离线映射。"""

    requests: list[dict[str, Any]] = []
    opened: list[asyncio.AbstractEventLoop] = []
    async_closed: list[asyncio.AbstractEventLoop] = []
    sync_closed: list[bool] = []

    candidate = {
        "operation": "UPSERT",
        "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
        "kind": "POSITION_PLAN_V1",
        "payload": {"target_budget": "300", "currency": "USD"},
        "origin": "USER_STATED_INTENT",
        "evidence_quote": "长期配置 300 美元",
        "replaces_candidate_id": None,
        "replaces_candidate_revision": None,
    }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "offline-gemini-key"
        payload = json.loads(request.content)
        requests.append(payload)
        parts: list[dict[str, object]]
        if len(requests) % 2:
            parts = [{"functionCall": {"name": "get_quote", "args": {"ticker": "GOOG"}}}]
        else:
            returned = [
                part["functionResponse"]
                for content in payload["contents"]
                for part in content.get("parts", [])
                if "functionResponse" in part
            ]
            assert len(returned) == 1 and returned[0]["name"] == "get_quote"
            observation = json.loads(returned[0]["response"]["return_value"])
            assert observation["status"] == "OK"
            assert observation["data"] == {"price": "210"}
            final: dict[str, object] = {"answer": "已核对。", "source_refs": []}
            if len(requests) == 4:
                final["candidate"] = candidate
            else:
                final["candidate"] = None
            parts = [{"text": json.dumps(final, ensure_ascii=False)}]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}
                ],
                "modelVersion": "gemini-3.8-flash",
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
            },
        )

    def client_factory(**kwargs: Any) -> SDKClient:
        opened.append(asyncio.get_running_loop())
        assert kwargs["vertexai"] is False
        assert kwargs["api_key"] == "offline-gemini-key"
        options = kwargs["http_options"]
        assert isinstance(options, HttpOptions)
        assert options.timeout == 60_000
        assert options.retry_options is not None and options.retry_options.attempts == 1
        client = SDKClient(
            api_key=kwargs["api_key"],
            vertexai=False,
            http_options=HttpOptions(
                base_url=options.base_url,
                retry_options=options.retry_options,
                httpx_async_client=httpx.AsyncClient(
                    transport=httpx.MockTransport(respond), trust_env=False
                ),
            ),
        )
        original_async_close = client.aio.aclose
        original_close = client.close

        async def async_close() -> None:
            async_closed.append(asyncio.get_running_loop())
            await original_async_close()

        def sync_close() -> None:
            sync_closed.append(True)
            original_close()

        monkeypatch.setattr(client.aio, "aclose", async_close)
        monkeypatch.setattr(client, "close", sync_close)
        return client

    monkeypatch.setattr(gemini_runtime, "Client", client_factory)
    runtime = create_pydantic_ai_runtime(_settings())
    assert runtime.provider_name == "GOOGLE_GEMINI"
    assert runtime._model_name == "gemini-3.8-flash"
    assert runtime._output_mechanism == "NATIVE"
    assert runtime.max_retries == 0

    regular_result = runtime.run(_request(strategy_candidates_enabled=True))
    candidate_result = runtime.run(_request(strategy_candidates_enabled=True))

    for result in (regular_result, candidate_result):
        assert result.status is AgentRunStatus.COMPLETED
        assert result.final_candidate is not None
        assert parse_structured_answer(result.final_candidate).answer == "已核对。"
        assert [entry.name for entry in result.tool_trace] == ["get_quote"]
    assert regular_result.strategy_draft is None
    assert candidate_result.strategy_draft is not None
    assert candidate_result.strategy_draft.scope.ticker == "GOOG"
    assert isinstance(candidate_result.strategy_draft.payload, PositionPlanPayload)
    assert candidate_result.strategy_draft.payload.target_budget == 300

    assert len(requests) == 4
    assert opened == async_closed and len(opened) == 2
    assert opened[0] is not opened[1]
    assert sync_closed == [True, True]
    for payload in requests:
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        schema = payload["generationConfig"]["responseJsonSchema"]
        assert "answer" in schema["required"]
        assert "source_refs" in schema["required"]
        assert "candidate" in schema["properties"]
        assert "WEB_RESEARCH" not in json.dumps(schema)
        assert "final_investment_answer" not in str(payload.get("tools"))
        assert "googleSearch" not in str(payload.get("tools"))


@pytest.mark.parametrize("key", [None, "", " "])
def test_missing_google_key_fails_without_other_credentials_or_network(
    monkeypatch: pytest.MonkeyPatch,
    key: str | None,
) -> None:
    """Google Final 不得使用 LLM_API_KEY 或默认凭据兜底。"""

    def unexpected_client(**kwargs: Any) -> SDKClient:
        raise AssertionError("缺少 Gemini Key 时不得创建 Provider Client")

    monkeypatch.setattr(gemini_runtime, "Client", unexpected_client)
    runtime = create_pydantic_ai_runtime(_settings(key))

    result = runtime.run(_request())

    assert result.status is AgentRunStatus.FAILED
    assert result.failure_code == "MODEL_CREDENTIAL_MISSING"
    assert result.tool_trace == ()
