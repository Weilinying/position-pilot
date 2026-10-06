"""应用依赖装配入口。"""

from functools import lru_cache

from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.application.auth_service import AuthService
from position_pilot.application.conversation_agent import ConversationInvestmentAgent
from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.market_context_service import MarketContextService
from position_pilot.application.market_data_service import MarketDataService
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.news_service import NewsService
from position_pilot.application.opening_import_service import OpeningImportService
from position_pilot.application.portfolio_chart_service import PortfolioChartService
from position_pilot.application.portfolio_service import PortfolioService
from position_pilot.application.portfolio_summary_service import PortfolioSummaryService
from position_pilot.application.portfolio_valuation_service import PortfolioValuationService
from position_pilot.application.recognition_service import RecognitionService
from position_pilot.application.strategy_service import StrategyService
from position_pilot.config import get_settings
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory
from position_pilot.integrations.aliyun_vision import AliyunVisionProvider
from position_pilot.integrations.alpaca_market_data import create_alpaca_market_data_provider
from position_pilot.integrations.alpaca_news import create_alpaca_news_provider
from position_pilot.integrations.finnhub_asset_metadata import FinnhubAssetMetadataProvider
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime


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
def get_market_data_service() -> MarketDataService:
    """装配 Portfolio 估值与 Agent 共用的行情边界。"""

    return MarketDataService(create_alpaca_market_data_provider(get_settings()))


@lru_cache
def get_portfolio_valuation_service() -> PortfolioValuationService:
    """装配当前 Portfolio 的确定性估值服务。"""

    return PortfolioValuationService(get_portfolio_service(), get_market_data_service())


@lru_cache
def get_portfolio_summary_service() -> PortfolioSummaryService:
    """装配复用同一账本快照的首页聚合服务。"""

    return PortfolioSummaryService(get_portfolio_service(), get_portfolio_valuation_service())


@lru_cache
def get_portfolio_chart_service() -> PortfolioChartService:
    """装配固定用户资产范围的历史图表服务。"""

    return PortfolioChartService(get_portfolio_service(), get_market_data_service())


@lru_cache
def get_recognition_service() -> RecognitionService:
    """装配进程内共享的 qwen3-vl-flash Recognition Application Service。"""

    settings = get_settings()
    # 仅阿里云 Final 可与阿里云 Vision 共用凭据；其他 Provider 不得跨端点回退。
    vision_api_key = _secret_value(settings.vision_api_key)
    if vision_api_key is None and settings.llm_provider == "ALIYUN_MODEL_STUDIO":
        vision_api_key = _secret_value(settings.llm_api_key)
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
        get_auth_service(),
        get_portfolio_service(),
    )


@lru_cache
def get_investment_agent() -> NativeInvestmentAgent:
    """只装配 PydanticAI Production Runtime 的 Investment Agent。"""

    settings = get_settings()
    market_data_service = get_market_data_service()
    news_service = NewsService(create_alpaca_news_provider(settings))
    runtime = create_pydantic_ai_runtime(settings)
    return NativeInvestmentAgent(
        get_portfolio_service(),
        market_data_service,
        runtime,
        news=news_service,
        market_context=MarketContextService(market_data_service),
    )


@lru_cache
def get_conversation_service() -> ConversationService:
    """装配 Account-owned Conversation Service 与同一 Production Agent。"""

    return ConversationService(
        SqlAlchemyConversationUnitOfWorkFactory(get_session_factory()),
        agent=ConversationInvestmentAgent(get_investment_agent(), get_strategy_service()),
        strategy_repository_factory=conversation_strategy_repository,
    )


def _secret_value(secret: SecretStr | None) -> str | None:
    """提取非空 SecretStr 值；不在配置或装配层打印凭据。"""

    if secret is None:
        return None
    normalized = secret.get_secret_value().strip()
    return normalized or None


@lru_cache
def get_strategy_service() -> StrategyService:
    """独立意图事务服务，共用既有 PostgreSQL Session Factory。"""
    from position_pilot.infrastructure.strategy_unit_of_work import (
        SqlAlchemyStrategyUnitOfWorkFactory,
    )

    return StrategyService(SqlAlchemyStrategyUnitOfWorkFactory(get_session_factory()))
