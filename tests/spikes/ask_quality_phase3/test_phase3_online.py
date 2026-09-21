"""Phase 3 固定模型与两条 Research 路径的显式 Opt-in Live Smoke。"""

import os
from collections.abc import Mapping
from dataclasses import replace

import pytest

from position_pilot.application.llm import LLMMessage, LLMRole, LLMToolDefinition
from position_pilot.integrations.aliyun_llm import AliyunLLMProvider

from .contracts import (
    ResearchRequest,
    ResearchStatus,
    RuntimeBudget,
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
    SourceRecord,
)
from .current_runtime import CurrentRuntimeCandidate, FunctionToolExecutor, ToolObservation
from .experiment_contract import EXPERIMENT_MODEL
from .harness import RuntimeCandidate
from .openai_agents_runtime import OpenAIAgentsRuntimeCandidate, build_qwen_agents_model
from .pydantic_runtime import PydanticRuntimeCandidate, build_alibaba_chat_model
from .research_candidates import (
    AlibabaNativeResearchCandidate,
    AlibabaResponsesGateway,
    ApplicationOwnedResearchCandidate,
    BraveSearchProvider,
    ControlledPageFetcher,
    HttpxTransport,
)

pytestmark = [
    pytest.mark.online,
    pytest.mark.skipif(
        os.getenv("RUN_PHASE3_LIVE") != "1",
        reason="需要显式启用 Phase 3 Live Smoke",
    ),
]


def _alibaba_config() -> tuple[str, str]:
    """只读取进程环境，不读取 Repository .env。"""

    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    if not api_key or not base_url:
        pytest.skip("需要显式 LLM_API_KEY 与 LLM_BASE_URL")
    return api_key, base_url


def _runtime_input() -> RuntimeInput:
    """使用无 Tool 的最小固定模型 Smoke。"""

    return RuntimeInput(
        conversation=(LLMMessage(LLMRole.USER, "只回答：Phase 3 runtime smoke ok"),),
        current_turn_context={"purpose": "provider-compatibility-smoke"},
        portfolio_context={"cash": "UNKNOWN", "positions": []},
        confirmed_strategy=(),
        tools=(),
        budget=RuntimeBudget(2, 1, 1, 1, 30),
    )


def _runtime_tool_input(*, multi_round: bool = False) -> RuntimeInput:
    """使用确定性本地 Tool 验证真实模型 Tool Calling 兼容性。"""

    prompt = (
        "先调用 search_web 搜索 GOOG official filing，再使用返回的 URL 调用 fetch_page，"
        "最后简短说明已经读取正文。"
        if multi_round
        else "调用 get_current_quote 查询 GOOG，然后只回答已取得报价。"
    )
    tool_names = ("search_web", "fetch_page") if multi_round else ("get_current_quote",)
    definitions = {
        "get_current_quote": LLMToolDefinition(
            "get_current_quote",
            "读取当前报价；本测试必须调用一次。",
            {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
                "additionalProperties": False,
            },
        ),
        "search_web": LLMToolDefinition(
            "search_web",
            "搜索公开网页并返回可读取 URL；本测试必须先调用。",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        "fetch_page": LLMToolDefinition(
            "fetch_page",
            "读取 search_web 返回的公开 URL；搜索后必须调用。",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        ),
    }
    return replace(
        _runtime_input(),
        conversation=(LLMMessage(LLMRole.USER, prompt),),
        tools=tuple(definitions[name] for name in tool_names),
        budget=RuntimeBudget(4, 3, 1, 1, 30),
    )


def _runtime_executors(
    calls: list[tuple[str, Mapping[str, object]]],
) -> dict[str, FunctionToolExecutor]:
    """返回无网络、无副作用的确定性 Tool，并记录真实模型参数。"""

    def quote(arguments: Mapping[str, object]) -> ToolObservation:
        calls.append(("get_current_quote", arguments))
        return ToolObservation(
            "OK",
            {"ticker": arguments.get("ticker"), "price": "210.25"},
            (SourceRecord("quote-live-1", "FIXED_LIVE_TOOL", None),),
        )

    def search(arguments: Mapping[str, object]) -> ToolObservation:
        calls.append(("search_web", arguments))
        return ToolObservation(
            "OK",
            {
                "query": arguments.get("query"),
                "results": [{"url": "https://example.test/filing"}],
            },
            (
                SourceRecord(
                    "search-live-1",
                    "FIXED_LIVE_TOOL",
                    "https://example.test/filing",
                ),
            ),
        )

    def fetch(arguments: Mapping[str, object]) -> ToolObservation:
        calls.append(("fetch_page", arguments))
        return ToolObservation(
            "OK",
            {"url": arguments.get("url"), "text": "固定公开文件正文。"},
            (
                SourceRecord(
                    "fetch-live-1",
                    "FIXED_LIVE_TOOL",
                    "https://example.test/filing",
                ),
            ),
        )

    return {
        "get_current_quote": FunctionToolExecutor(quote),
        "search_web": FunctionToolExecutor(search),
        "fetch_page": FunctionToolExecutor(fetch),
    }


def _assert_usage_observation(result: RuntimeResult) -> None:
    """接受 Provider 未回传 Usage，但必须明确标记为 UNKNOWN。"""

    usage = result.usage
    warnings = result.warnings
    if usage is None:
        assert "USAGE_NOT_REPORTED" in warnings
    else:
        assert usage.total_tokens > 0


def test_fixed_model_current_runtime_live_smoke() -> None:
    """Current Runtime 使用固定 qwen3.7-max，而非 Production Default。"""

    api_key, base_url = _alibaba_config()
    provider = AliyunLLMProvider(
        api_key=api_key,
        base_url=base_url,
        model=EXPERIMENT_MODEL,
    )

    result = CurrentRuntimeCandidate(provider, {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    assert result.usage is not None


def test_fixed_model_pydantic_runtime_live_smoke() -> None:
    """PydanticAI 使用原生 AlibabaProvider 接入同一固定模型。"""

    api_key, base_url = _alibaba_config()
    model = build_alibaba_chat_model(
        EXPERIMENT_MODEL,
        api_key=api_key,
        base_url=base_url,
    )

    result = PydanticRuntimeCandidate(model, {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    _assert_usage_observation(result)


def test_fixed_model_openai_agents_runtime_live_smoke() -> None:
    """Agents SDK 经 Chat Completions Adapter 接入同一 Qwen Endpoint。"""

    api_key, base_url = _alibaba_config()
    model = build_qwen_agents_model(
        EXPERIMENT_MODEL,
        api_key=api_key,
        base_url=base_url,
    )

    result = OpenAIAgentsRuntimeCandidate(model, {}).run(_runtime_input())

    assert result.status is RuntimeExecutionStatus.COMPLETED
    _assert_usage_observation(result)


@pytest.mark.parametrize("runtime_name", ["current", "pydantic-ai", "openai-agents-sdk"])
@pytest.mark.parametrize("multi_round", [False, True], ids=["one-tool", "multi-tool"])
def test_fixed_model_runtime_tool_calling_live_smoke(
    runtime_name: str,
    multi_round: bool,
) -> None:
    """真实模型验证 Tool 选择、参数、轮次、Usage 与 Latency。"""

    api_key, base_url = _alibaba_config()
    calls: list[tuple[str, Mapping[str, object]]] = []
    executors = _runtime_executors(calls)
    runtime_input = _runtime_tool_input(multi_round=multi_round)
    if runtime_name == "current":
        provider = AliyunLLMProvider(
            api_key=api_key,
            base_url=base_url,
            model=EXPERIMENT_MODEL,
        )
        candidate: RuntimeCandidate = CurrentRuntimeCandidate(provider, executors)
    elif runtime_name == "pydantic-ai":
        pydantic_model = build_alibaba_chat_model(
            EXPERIMENT_MODEL,
            api_key=api_key,
            base_url=base_url,
        )
        candidate = PydanticRuntimeCandidate(pydantic_model, executors)
    else:
        agents_model = build_qwen_agents_model(
            EXPERIMENT_MODEL,
            api_key=api_key,
            base_url=base_url,
        )
        candidate = OpenAIAgentsRuntimeCandidate(agents_model, executors)

    result = candidate.run(runtime_input)

    expected_tools = ["search_web", "fetch_page"] if multi_round else ["get_current_quote"]
    if result.status is not RuntimeExecutionStatus.COMPLETED:
        assert result.status is RuntimeExecutionStatus.CANDIDATE_FAILURE
        assert result.failure == "UNOBSERVED_SOURCE_REFERENCE"
    assert [name for name, _ in calls] == expected_tools
    assert [event.tool_name for event in result.tool_trace] == expected_tools
    _assert_usage_observation(result)
    assert result.latency_ms is not None
    assert result.latency_ms > 0
    if multi_round:
        assert calls[1][1]["url"] == "https://example.test/filing"
    else:
        assert calls[0][1]["ticker"] == "GOOG"


def test_fixed_model_alibaba_native_research_live_smoke() -> None:
    """Native Research 不为搜索能力临时更换固定模型。"""

    api_key, base_url = _alibaba_config()
    candidate = AlibabaNativeResearchCandidate(
        AlibabaResponsesGateway(api_key=api_key, base_url=base_url),
        model=EXPERIMENT_MODEL,
    )

    result = candidate.research(
        ResearchRequest("GOOG", "latest official filing", "last-7-days", "Alphabet")
    )

    assert result.status in {ResearchStatus.COMPLETED, ResearchStatus.NO_RESULTS}
    if result.status is ResearchStatus.COMPLETED:
        assert result.sources
        assert result.search_count >= 1


def test_application_owned_research_live_smoke() -> None:
    """一个 Search Provider 加独立受控 Fetch 完成 Application-owned Smoke。"""

    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        pytest.skip("需要显式 BRAVE_SEARCH_API_KEY")
    transport = HttpxTransport()
    candidate = ApplicationOwnedResearchCandidate(
        BraveSearchProvider(transport, api_key=api_key),
        ControlledPageFetcher(transport),
    )

    result = candidate.research(
        ResearchRequest("GOOG", "latest official filing", "last-7-days", "Alphabet")
    )

    assert result.status in {ResearchStatus.COMPLETED, ResearchStatus.PARTIAL_SUCCESS}
    assert result.sources
    assert result.search_count == 1
