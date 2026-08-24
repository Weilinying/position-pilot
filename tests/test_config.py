"""运行时配置测试。"""

import pytest
from pydantic import ValidationError

from position_pilot.config import Settings


def test_settings_reads_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """数据库连接地址应来自环境变量。"""

    database_url = "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert str(settings.database_url) == database_url


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少数据库连接地址时应明确拒绝启动数据库能力。"""

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_rejects_non_psycopg_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    """数据库连接必须使用已批准的同步 psycopg 驱动。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://position_pilot:secret@localhost:5432/position_pilot",
    )

    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_reads_alpaca_credentials_as_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alpaca Credential 应从环境变量读取且 repr 不暴露明文。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.alpaca_api_key_id is not None
    assert settings.alpaca_api_key_id.get_secret_value() == "key-id"
    assert "secret-key" not in repr(settings)


@pytest.mark.parametrize("timeout", ["0", "nan", "61"])
def test_settings_rejects_invalid_alpaca_timeout(
    monkeypatch: pytest.MonkeyPatch,
    timeout: str,
) -> None:
    """外部请求 Timeout 必须处于有限安全范围。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("ALPACA_REQUEST_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError, match="ALPACA_REQUEST_TIMEOUT_SECONDS"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_requires_https_alpaca_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alpaca Credential 不得通过明文 HTTP 发送。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("ALPACA_DATA_BASE_URL", "http://data.alpaca.example")

    with pytest.raises(ValidationError, match="必须使用 HTTPS"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_uses_configurable_generic_llm_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认模型属于通用环境配置，不成为业务类型。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert str(settings.llm_base_url) == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.llm_model == "qwen3.7-plus"
    assert settings.llm_api_key is None


def test_settings_reads_llm_api_key_as_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM Credential 应从通用变量读取且 repr 不暴露明文。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("LLM_MODEL", " replacement-model ")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "llm-secret"
    assert settings.llm_model == "replacement-model"
    assert "llm-secret" not in repr(settings)


@pytest.mark.parametrize("timeout", ["0", "nan", "121"])
def test_settings_rejects_invalid_llm_timeout(
    monkeypatch: pytest.MonkeyPatch,
    timeout: str,
) -> None:
    """LLM Timeout 必须处于有限安全范围。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError, match="LLM_REQUEST_TIMEOUT_SECONDS"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_requires_https_llm_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM Credential 与 Portfolio Context 不得通过明文 HTTP 发送。"""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot",
    )
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.example.test/v1")

    with pytest.raises(ValidationError, match="LLM_BASE_URL"):
        Settings(_env_file=None)  # type: ignore[call-arg]
