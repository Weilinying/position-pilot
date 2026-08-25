"""应用依赖装配入口。"""

from functools import lru_cache

from position_pilot.application.investment_agent import InvestmentAgent
from position_pilot.application.market_data_service import MarketDataService
from position_pilot.application.portfolio_service import PortfolioService
from position_pilot.config import get_settings
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory
from position_pilot.integrations.aliyun_llm import create_aliyun_llm_provider
from position_pilot.integrations.alpaca_market_data import create_alpaca_market_data_provider


@lru_cache
def get_portfolio_service() -> PortfolioService:
    """装配进程内共享的 Portfolio Application Service。"""

    settings = get_settings()
    engine = create_database_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)
    return PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))


@lru_cache
def get_investment_agent() -> InvestmentAgent:
    """按已批准依赖方向装配进程内共享 InvestmentAgent。"""

    settings = get_settings()
    market_data_service = MarketDataService(create_alpaca_market_data_provider(settings))
    llm_provider = create_aliyun_llm_provider(settings)
    return InvestmentAgent(get_portfolio_service(), market_data_service, llm_provider)
