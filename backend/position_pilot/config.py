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
    finnhub_api_key: SecretStr | None = None
    finnhub_base_url: AnyHttpUrl = AnyHttpUrl("https://finnhub.io/api/v1")
    finnhub_request_timeout_seconds: float = 10.0
    llm_base_url: AnyHttpUrl = AnyHttpUrl("https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_api_key: SecretStr | None = None
    llm_model: str = "deepseek-v4-pro-0813"
    llm_request_timeout_seconds: float = 30.0
    vision_base_url: AnyHttpUrl = AnyHttpUrl("https://dashscope.aliyuncs.com/compatible-mode/v1")
    vision_api_key: SecretStr | None = None
    vision_model: str = "qwen3-vl-flash"
    vision_request_timeout_seconds: float = 30.0

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

    @field_validator("finnhub_request_timeout_seconds")
    @classmethod
    def require_positive_finnhub_timeout(cls, value: float) -> float:
        """限制 Asset Metadata Provider 请求等待时间。"""

        if not isfinite(value) or value <= 0 or value > 60:
            raise ValueError("FINNHUB_REQUEST_TIMEOUT_SECONDS 必须在 0 到 60 秒之间")
        return value

    @field_validator("finnhub_base_url")
    @classmethod
    def require_https_finnhub_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """防止 Finnhub Credential 被发送到明文 HTTP endpoint。"""

        if value.scheme != "https":
            raise ValueError("FINNHUB_BASE_URL 必须使用 HTTPS")
        return value

    @field_validator("llm_request_timeout_seconds")
    @classmethod
    def require_positive_llm_timeout(cls, value: float) -> float:
        """限制 LLM 请求等待时间，避免 Agent Request 无限阻塞。"""

        if not isfinite(value) or value <= 0 or value > 120:
            raise ValueError("LLM_REQUEST_TIMEOUT_SECONDS 必须在 0 到 120 秒之间")
        return value

    @field_validator("llm_base_url")
    @classmethod
    def require_https_llm_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """防止 LLM Credential 与 Portfolio Context 通过明文 HTTP 发送。"""

        if value.scheme != "https":
            raise ValueError("LLM_BASE_URL 必须使用 HTTPS")
        return value

    @field_validator("llm_model")
    @classmethod
    def require_nonempty_llm_model(cls, value: str) -> str:
        """模型是可覆盖配置，但不能为空或只包含空白。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM_MODEL 不能为空")
        return normalized

    @field_validator("vision_request_timeout_seconds")
    @classmethod
    def require_positive_vision_timeout(cls, value: float) -> float:
        """限制 Vision Provider 请求等待时间，避免图片识别无限阻塞。"""

        if not isfinite(value) or value <= 0 or value > 120:
            raise ValueError("VISION_REQUEST_TIMEOUT_SECONDS 必须在 0 到 120 秒之间")
        return value

    @field_validator("vision_base_url")
    @classmethod
    def require_https_vision_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """防止 Vision Credential 与截图通过明文 HTTP 发送。"""

        if value.scheme != "https":
            raise ValueError("VISION_BASE_URL 必须使用 HTTPS")
        return value

    @field_validator("vision_model")
    @classmethod
    def require_nonempty_vision_model(cls, value: str) -> str:
        """Vision 模型是可覆盖配置，但不能为空或只包含空白。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("VISION_MODEL 不能为空")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """返回进程内共享的已校验配置。"""

    return Settings()  # type: ignore[call-arg]
