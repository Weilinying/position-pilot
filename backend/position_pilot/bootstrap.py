"""应用依赖装配入口。"""

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.auth_service import AuthService
from position_pilot.application.investment_agent import InvestmentAgent
from position_pilot.application.market_context_service import MarketContextService
from position_pilot.application.market_data_service import MarketDataService
from position_pilot.application.news_service import NewsService
from position_pilot.application.portfolio_service import PortfolioService
from position_pilot.config import get_settings
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory
from position_pilot.integrations.aliyun_llm import create_aliyun_llm_provider
from position_pilot.integrations.alpaca_market_data import create_alpaca_market_data_provider
from position_pilot.integrations.alpaca_news import create_alpaca_news_provider


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
