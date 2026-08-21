"""运行时配置。"""

from functools import lru_cache
from math import isfinite

from pydantic import AnyHttpUrl, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取应用运行时配置。"""

    database_url: PostgresDsn
    alpaca_api_key_id: SecretStr | None = None
    alpaca_api_secret_key: SecretStr | None = None
    alpaca_data_base_url: AnyHttpUrl = AnyHttpUrl("https://data.alpaca.markets")
    alpaca_request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def require_sync_psycopg_driver(cls, value: PostgresDsn) -> PostgresDsn:
        """确保数据库地址与已批准的同步 psycopg 方案一致。"""

        if value.scheme != "postgresql+psycopg":
            raise ValueError("DATABASE_URL 必须使用 postgresql+psycopg 驱动")
        return value

    @field_validator("alpaca_request_timeout_seconds")
    @classmethod
    def require_positive_alpaca_timeout(cls, value: float) -> float:
        """避免外部 Provider 请求无限等待或立即超时。"""

        if not isfinite(value) or value <= 0 or value > 60:
            raise ValueError("ALPACA_REQUEST_TIMEOUT_SECONDS 必须在 0 到 60 秒之间")
        return value

    @field_validator("alpaca_data_base_url")
    @classmethod
    def require_https_alpaca_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """防止 Market Data Credential 被发送到明文 HTTP endpoint。"""

        if value.scheme != "https":
            raise ValueError("ALPACA_DATA_BASE_URL 必须使用 HTTPS")
        return value


@lru_cache
def get_settings() -> Settings:
    """返回进程内共享的已校验配置。"""

    return Settings()  # type: ignore[call-arg]
