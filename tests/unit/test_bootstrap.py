"""M9 Provider 运行时依赖装配测试。"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr

from position_pilot import bootstrap
from position_pilot.application.agent_runtime import DEFAULT_WALL_CLOCK_BUDGET_SECONDS
from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.conversation_agent import ConversationInvestmentAgent
from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.recognition_service import RecognitionService
from position_pilot.config import Settings
from position_pilot.integrations.aliyun_vision import AliyunVisionProvider
from position_pilot.integrations.finnhub_asset_metadata import FinnhubAssetMetadataProvider

DATABASE_URL = "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"


@pytest.fixture(autouse=True)
def clear_provider_service_caches() -> Iterator[None]:
    """每个测试隔离进程内 Provider Service Cache。"""

    bootstrap.get_asset_metadata_service.cache_clear()
    bootstrap.get_conversation_service.cache_clear()
    bootstrap.get_investment_agent.cache_clear()
    bootstrap.get_recognition_service.cache_clear()
    yield
    bootstrap.get_asset_metadata_service.cache_clear()
    bootstrap.get_conversation_service.cache_clear()
    bootstrap.get_investment_agent.cache_clear()
    bootstrap.get_recognition_service.cache_clear()


def make_settings(
    *,
    finnhub_api_key: SecretStr | None = None,
    llm_api_key: SecretStr | None = None,
    vision_api_key: SecretStr | None = None,
    llm_provider: str = "ALIYUN_MODEL_STUDIO",
    gemini_api_key: SecretStr | None = None,
) -> Settings:
    """创建不读取本地 .env 的固定配置。"""

    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn(DATABASE_URL),
        finnhub_api_key=finnhub_api_key,
        finnhub_base_url=AnyHttpUrl("https://finnhub.example.test/api/v1"),
        finnhub_request_timeout_seconds=9,
        llm_provider=llm_provider,
        llm_model=(
            "gemini-3.8-flash" if llm_provider == "GOOGLE_GEMINI" else "deepseek-v4-pro-0813"
        ),
        llm_api_key=llm_api_key,
        gemini_api_key=gemini_api_key,
        vision_base_url=AnyHttpUrl("https://vision.example.test/compatible-mode/v1"),
        vision_api_key=vision_api_key,
        vision_model="configured-qwen3-vl-flash",
        vision_request_timeout_seconds=11,
    )


def test_asset_metadata_service_uses_finnhub_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset Metadata Service 应由 Finnhub 配置装配且保持 Application Boundary。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(finnhub_api_key=SecretStr("finnhub-secret")),
    )

    service = bootstrap.get_asset_metadata_service()

    assert isinstance(service, AssetMetadataService)
    provider = service._provider
    assert isinstance(provider, FinnhubAssetMetadataProvider)
    assert provider._api_key == "finnhub-secret"
    assert provider._base_url == "https://finnhub.example.test/api/v1"
    assert provider._timeout_seconds == 9


def test_recognition_service_reuses_llm_key_when_vision_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vision Key 缺失时应由 Bootstrap 复用 LLM Key，而非修改 Settings 语义。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(
            finnhub_api_key=None,
            llm_api_key=SecretStr("shared-llm-secret"),
            vision_api_key=None,
        ),
    )

    service = bootstrap.get_recognition_service()

    assert isinstance(service, RecognitionService)
    provider = service._provider
    assert isinstance(provider, AliyunVisionProvider)
    assert provider._api_key == "shared-llm-secret"
    assert provider._base_url == "https://vision.example.test/compatible-mode/v1"
    assert provider._model == "configured-qwen3-vl-flash"
    assert provider._timeout_seconds == 11


def test_recognition_service_prefers_explicit_vision_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式 Vision Key 应优先于通用 LLM Key。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(
            llm_api_key=SecretStr("shared-llm-secret"),
            vision_api_key=SecretStr("dedicated-vision-secret"),
        ),
    )

    service = bootstrap.get_recognition_service()

    provider = service._provider
    assert isinstance(provider, AliyunVisionProvider)
    assert provider._api_key == "dedicated-vision-secret"


def test_gemini_key_is_not_reused_for_vision_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini Final Credential 不得回退为 Aliyun Vision Credential。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(
            llm_provider="GOOGLE_GEMINI",
            llm_api_key=SecretStr("unrelated-llm-secret"),
            gemini_api_key=SecretStr("independent-gemini-secret"),
        ),
    )

    service = bootstrap.get_recognition_service()

    provider = service._provider
    assert isinstance(provider, AliyunVisionProvider)
    assert provider._api_key is None


def test_gemini_provider_uses_only_explicit_vision_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini 配置下只有显式 Vision Key 可用于 Vision Provider。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(
            llm_provider="GOOGLE_GEMINI",
            llm_api_key=SecretStr("unrelated-llm-secret"),
            gemini_api_key=SecretStr("independent-gemini-secret"),
            vision_api_key=SecretStr("dedicated-vision-secret"),
        ),
    )

    service = bootstrap.get_recognition_service()

    provider = service._provider
    assert isinstance(provider, AliyunVisionProvider)
    assert provider._api_key == "dedicated-vision-secret"


@pytest.mark.parametrize("llm_provider", ["GOOGLE_GEMINI", "ALIYUN_MODEL_STUDIO"])
def test_investment_agent_bootstrap_uses_only_pydantic_ai_runtime(
    monkeypatch: pytest.MonkeyPatch,
    llm_provider: str,
) -> None:
    """切换 Final Provider 不改变工具集合，遗留 Research 开关也不能暴露 Search。"""

    monkeypatch.setenv("RESEARCH_ENABLED", "1")
    settings = make_settings(
        llm_api_key=SecretStr("runtime-secret"),
        gemini_api_key=SecretStr("gemini-runtime-secret"),
        llm_provider=llm_provider,
    )
    runtime = object()
    portfolio_reader = object()
    market_data = object()
    monkeypatch.setattr(bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(bootstrap, "get_portfolio_service", lambda: portfolio_reader)
    monkeypatch.setattr(bootstrap, "get_market_data_service", lambda: market_data)
    monkeypatch.setattr(
        bootstrap,
        "create_alpaca_news_provider",
        lambda received: object(),
    )
    monkeypatch.setattr(
        bootstrap,
        "create_pydantic_ai_runtime",
        lambda received: runtime,
    )

    agent = bootstrap.get_investment_agent()

    assert isinstance(agent, NativeInvestmentAgent)
    assert agent._runtime is runtime
    assert agent._portfolio_reader is portfolio_reader
    assert agent._market_data is market_data
    assert set(agent._tool_catalog.names) == {
        "get_current_quote",
        "get_recent_price_history",
        "get_recent_news",
        "get_market_context",
    }


@pytest.mark.parametrize("http_timeout_seconds", [10.0, 60.0])
def test_conversation_service_reuses_production_agent_and_database_factory(
    monkeypatch: pytest.MonkeyPatch,
    http_timeout_seconds: float,
) -> None:
    """Turn 租约覆盖正式总预算，不随单次 HTTP Timeout 缩短。"""

    investment_agent = object()
    session_factory = object()
    settings = make_settings().model_copy(
        update={"native_llm_request_timeout_seconds": http_timeout_seconds}
    )
    monkeypatch.setattr(bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(bootstrap, "get_investment_agent", lambda: investment_agent)
    monkeypatch.setattr(bootstrap, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(bootstrap, "get_strategy_service", lambda: object())

    service = bootstrap.get_conversation_service()

    assert isinstance(service, ConversationService)
    assert isinstance(service._agent, ConversationInvestmentAgent)
    assert service._agent._agent is investment_agent
    assert DEFAULT_WALL_CLOCK_BUDGET_SECONDS == 60
    assert service._run_timeout == timedelta(seconds=65)
