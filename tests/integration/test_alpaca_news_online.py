"""真实 Alpaca Recent News 的显式启用 Smoke Test。"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from position_pilot.application.news_service import NewsQuery, NewsService
from position_pilot.domain.news import NewsStatus
from position_pilot.integrations.alpaca_news import AlpacaNewsProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]


def test_real_alpaca_news_entitlement_and_attribution() -> None:
    """显式启用时验证 News Endpoint 权限、窗口和来源归因。"""

    if os.getenv("RUN_ALPACA_ONLINE_TESTS") != "1":
        pytest.skip("需要 RUN_ALPACA_ONLINE_TESTS=1 才执行真实 Alpaca News 请求")
    api_key = os.getenv("ALPACA_API_KEY_ID")
    api_secret = os.getenv("ALPACA_API_SECRET_KEY")
    if not api_key or not api_secret:
        pytest.skip("Alpaca Credential 未配置")

    service = NewsService(
        AlpacaNewsProvider(
            api_key_id=api_key,
            api_secret_key=api_secret,
            base_url=os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"),
            timeout_seconds=float(os.getenv("ALPACA_REQUEST_TIMEOUT_SECONDS", "10")),
        )
    )
    end = datetime.now(UTC) - timedelta(minutes=15)

    result = service.get_recent_news(
        NewsQuery(
            ticker="AAPL",
            start=end - timedelta(days=5),
            end=end,
            limit=5,
        )
    )

    assert result.status in {NewsStatus.OK, NewsStatus.NO_NEWS_FOUND}
    if result.status is NewsStatus.OK:
        assert result.data is not None
        assert result.data.provider == "ALPACA"
        assert all(article.source for article in result.data.articles)
        assert all(article.updated_at <= end for article in result.data.articles)
