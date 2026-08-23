"""需要显式凭据与网络授权的 Alpaca 在线 Smoke Test。"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.domain.market_data import MarketDataStatus
from position_pilot.integrations.alpaca_market_data import AlpacaMarketDataProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]


def get_online_provider() -> AlpacaMarketDataProvider:
    """只有调用方显式启用时才读取本地 Alpaca Credential。"""

    if os.environ.get("RUN_ALPACA_ONLINE_TESTS") != "1":
        pytest.skip("需要 RUN_ALPACA_ONLINE_TESTS=1 才执行真实 Alpaca 请求")
    api_key_id = os.environ.get("ALPACA_API_KEY_ID")
    api_secret_key = os.environ.get("ALPACA_API_SECRET_KEY")
    if not api_key_id or not api_secret_key:
        pytest.skip("需要 ALPACA_API_KEY_ID 与 ALPACA_API_SECRET_KEY")
    return AlpacaMarketDataProvider(
        api_key_id=api_key_id,
        api_secret_key=api_secret_key,
    )


def test_alpaca_current_quote_online() -> None:
    """真实 Provider 应返回带市场时间的 IEX Quote。"""

    provider = get_online_provider()
    quote_result = provider.get_current_quote("GOOG")

    assert quote_result.status is MarketDataStatus.OK, (
        f"{quote_result.status}: {quote_result.message}"
    )
    assert quote_result.data is not None
    assert quote_result.data.last_trade_at.tzinfo is UTC


def test_alpaca_historical_bars_online() -> None:
    """真实 Provider 应返回至少一根延迟 SIP Daily Bar。"""

    provider = get_online_provider()
    now = datetime.now(UTC)
    bars_result = provider.get_historical_bars(
        HistoricalBarsQuery(
            ticker="GOOG",
            start=now - timedelta(days=14),
            end=now - timedelta(minutes=20),
            limit=20,
        )
    )

    assert bars_result.status is MarketDataStatus.OK, f"{bars_result.status}: {bars_result.message}"
    assert bars_result.data is not None
    assert bars_result.data.bars
