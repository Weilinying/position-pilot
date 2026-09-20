"""Phase 3 固定模型与两条 Research 路径的显式 Opt-in Live Smoke。"""

import os

import pytest

from position_pilot.application.llm import LLMMessage, LLMRole
from position_pilot.integrations.aliyun_llm import AliyunLLMProvider

from .contracts import (
    ResearchRequest,
    ResearchStatus,
    RuntimeBudget,
    RuntimeExecutionStatus,
    RuntimeInput,
)
from .current_runtime import CurrentRuntimeCandidate
from .experiment_contract import EXPERIMENT_MODEL
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
    assert result.usage is not None


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
