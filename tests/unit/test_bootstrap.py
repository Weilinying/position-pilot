"""M9 Provider 运行时依赖装配测试。"""

from collections.abc import Iterator

import pytest
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr

from position_pilot import bootstrap
from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.recognition_service import RecognitionService
from position_pilot.config import Settings
from position_pilot.integrations.aliyun_vision import AliyunVisionProvider
from position_pilot.integrations.massive_asset_metadata import MassiveAssetMetadataProvider

DATABASE_URL = "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"


@pytest.fixture(autouse=True)
def clear_provider_service_caches() -> Iterator[None]:
    """每个测试隔离进程内 Provider Service Cache。"""

    bootstrap.get_asset_metadata_service.cache_clear()
    bootstrap.get_recognition_service.cache_clear()
    yield
    bootstrap.get_asset_metadata_service.cache_clear()
    bootstrap.get_recognition_service.cache_clear()


def make_settings(
    *,
    massive_api_key: SecretStr | None = None,
    llm_api_key: SecretStr | None = None,
    vision_api_key: SecretStr | None = None,
) -> Settings:
    """创建不读取本地 .env 的固定配置。"""

    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn(DATABASE_URL),
        massive_api_key=massive_api_key,
        massive_base_url=AnyHttpUrl("https://massive.example.test"),
        massive_request_timeout_seconds=9,
        llm_api_key=llm_api_key,
        vision_base_url=AnyHttpUrl("https://vision.example.test/compatible-mode/v1"),
        vision_api_key=vision_api_key,
        vision_model="configured-qwen3-vl-flash",
        vision_request_timeout_seconds=11,
    )


def test_asset_metadata_service_uses_massive_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset Metadata Service 应由 Massive 配置装配且保持 Application Boundary。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(massive_api_key=SecretStr("massive-secret")),
    )

    service = bootstrap.get_asset_metadata_service()

    assert isinstance(service, AssetMetadataService)
    provider = service._provider
    assert isinstance(provider, MassiveAssetMetadataProvider)
    assert provider._api_key == "massive-secret"
    assert provider._base_url == "https://massive.example.test"
    assert provider._timeout_seconds == 9


def test_recognition_service_reuses_llm_key_when_vision_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vision Key 缺失时应由 Bootstrap 复用 LLM Key，而非修改 Settings 语义。"""

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: make_settings(
            massive_api_key=None,
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
