"""应用依赖装配入口。"""

from functools import lru_cache

from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.auth_service import AuthService
from position_pilot.application.investment_agent import InvestmentAgent
from position_pilot.application.market_context_service import MarketContextService
from position_pilot.application.market_data_service import MarketDataService
from position_pilot.application.news_service import NewsService
from position_pilot.application.opening_import_service import OpeningImportService
from position_pilot.application.portfolio_service import PortfolioService
from position_pilot.application.recognition_service import RecognitionService
from position_pilot.config import get_settings
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory
from position_pilot.integrations.aliyun_llm import create_aliyun_llm_provider
from position_pilot.integrations.aliyun_vision import AliyunVisionProvider
from position_pilot.integrations.alpaca_market_data import create_alpaca_market_data_provider
from position_pilot.integrations.alpaca_news import create_alpaca_news_provider
from position_pilot.integrations.finnhub_asset_metadata import FinnhubAssetMetadataProvider


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """让 Portfolio 与 Auth Service 共享同一数据库连接池。"""

    settings = get_settings()
    engine = create_database_engine(str(settings.database_url))
    return create_session_factory(engine)


@lru_cache
def get_portfolio_service() -> PortfolioService:
    """装配进程内共享的 Portfolio Application Service。"""

    return PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(get_session_factory()))


@lru_cache
def get_auth_service() -> AuthService:
    """装配进程内共享的本地 Auth Application Service。"""

    return AuthService(SqlAlchemyPortfolioUnitOfWorkFactory(get_session_factory()))


@lru_cache
def get_asset_metadata_service() -> AssetMetadataService:
    """装配进程内共享的 Finnhub Asset Metadata Application Service。"""

    settings = get_settings()
    provider = FinnhubAssetMetadataProvider(
        api_key=_secret_value(settings.finnhub_api_key),
        base_url=str(settings.finnhub_base_url),
        timeout_seconds=settings.finnhub_request_timeout_seconds,
    )
    return AssetMetadataService(provider)


@lru_cache
def get_recognition_service() -> RecognitionService:
    """装配进程内共享的 qwen3-vl-flash Recognition Application Service。"""

    settings = get_settings()
    # Vision Credential 可独立配置；未配置时复用通用 LLM Credential，减少本地凭据数量。
    vision_api_key = _secret_value(settings.vision_api_key) or _secret_value(settings.llm_api_key)
    provider = AliyunVisionProvider(
        api_key=vision_api_key,
        base_url=str(settings.vision_base_url),
        model=settings.vision_model,
        timeout_seconds=settings.vision_request_timeout_seconds,
    )
    return RecognitionService(provider)


@lru_cache
def get_opening_import_service() -> OpeningImportService:
    """装配不持久化 Draft 的 Opening Import Application Service。"""

    return OpeningImportService(
        get_asset_metadata_service(),
        get_auth_service(),
        get_portfolio_service(),
    )


@lru_cache
def get_investment_agent() -> InvestmentAgent:
    """按已批准依赖方向装配进程内共享 InvestmentAgent。"""

    settings = get_settings()
    market_data_service = MarketDataService(create_alpaca_market_data_provider(settings))
    news_service = NewsService(create_alpaca_news_provider(settings))
    llm_provider = create_aliyun_llm_provider(settings)
    return InvestmentAgent(
        get_portfolio_service(),
        market_data_service,
        llm_provider,
        news=news_service,
        market_context=MarketContextService(market_data_service),
    )


def _secret_value(secret: SecretStr | None) -> str | None:
    """提取非空 SecretStr 值；不在配置或装配层打印凭据。"""

    if secret is None:
        return None
    normalized = secret.get_secret_value().strip()
    return normalized or None
