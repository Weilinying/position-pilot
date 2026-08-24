"""真实 Aliyun LLM + 真实 Alpaca Market Data 的少量 Smoke Test。"""

import os
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.investment_agent import InvestmentAgent, InvestmentAnswer
from position_pilot.application.market_data_service import MarketDataService
from position_pilot.domain.portfolio import CashBalance, PortfolioState
from position_pilot.integrations.aliyun_llm import AliyunLLMProvider
from position_pilot.integrations.alpaca_market_data import AlpacaMarketDataProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]

USER_ID = UUID("00000000-0000-0000-0000-000000000201")


class FixedEmptyPortfolioReader:
    """隔离数据库，只让 Smoke Test 覆盖两个真实外部 Provider。"""

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        assert user_id == USER_ID
        return PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(USER_ID, Decimal("1000"), Decimal("300")),
            positions=(),
            transaction_count=0,
        )


def test_real_llm_and_market_data_complete_single_agent_round() -> None:
    """显式启用时验证真实 LLM 能调用真实 Current Quote 并形成 Final Answer。"""

    if os.getenv("RUN_INVESTMENT_AGENT_ONLINE") != "1":
        pytest.skip("需要显式启用真实 Agent Integration Smoke Test")
    llm_api_key = os.getenv("LLM_API_KEY")
    alpaca_key = os.getenv("ALPACA_API_KEY_ID")
    alpaca_secret = os.getenv("ALPACA_API_SECRET_KEY")
    if not llm_api_key or not alpaca_key or not alpaca_secret:
        pytest.skip("真实 LLM 或 Alpaca Credential 未配置")

    llm = AliyunLLMProvider(
        api_key=llm_api_key,
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("LLM_MODEL", "qwen3.7-plus"),
        timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")),
    )
    market_data = MarketDataService(
        AlpacaMarketDataProvider(
            api_key_id=alpaca_key,
            api_secret_key=alpaca_secret,
            base_url=os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"),
            timeout_seconds=float(os.getenv("ALPACA_REQUEST_TIMEOUT_SECONDS", "10")),
        )
    )
    agent = InvestmentAgent(FixedEmptyPortfolioReader(), market_data, llm)

    result = agent.answer(USER_ID, "GOOG 当前价格是多少？我目前有持仓吗？")

    assert isinstance(result, InvestmentAnswer)
    assert result.answer
