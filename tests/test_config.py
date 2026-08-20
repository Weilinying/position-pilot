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
