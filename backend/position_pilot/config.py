"""运行时配置。"""

from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取应用运行时配置。"""

    database_url: PostgresDsn

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


@lru_cache
def get_settings() -> Settings:
    """返回进程内共享的已校验配置。"""

    return Settings()  # type: ignore[call-arg]
