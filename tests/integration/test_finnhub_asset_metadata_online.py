"""需要显式凭据与网络授权的 Finnhub Asset Metadata Smoke Test。"""

import os

import pytest

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.domain.asset_metadata import AssetMetadataStatus
from position_pilot.integrations.finnhub_asset_metadata import FinnhubAssetMetadataProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]


def get_online_service() -> AssetMetadataService:
    """只读取显式导出的进程环境变量，不加载或检查仓库 `.env`。"""

    if os.getenv("RUN_M9_ONLINE_TESTS") != "1":
        pytest.skip("需要 RUN_M9_ONLINE_TESTS=1 才执行 M9 真实 Provider Smoke")
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        pytest.skip("需要显式导出 FINNHUB_API_KEY")
    return AssetMetadataService(
        FinnhubAssetMetadataProvider(
            api_key=api_key,
            base_url=os.getenv("FINNHUB_BASE_URL", "https://finnhub.io/api/v1"),
        )
    )


def test_finnhub_search_and_exact_validation_online() -> None:
    """真实 Provider 应覆盖常见股票、ETF 与无效 symbol。"""

    service = get_online_service()

    for symbol in ("AAPL", "GOOG"):
        search_result = service.search(symbol, limit=5)
        assert search_result.status is AssetMetadataStatus.OK, (
            f"{symbol} search: {search_result.status}: {search_result.message}"
        )
        assert any(candidate.canonical_symbol == symbol for candidate in search_result.candidates)

    for symbol in ("AAPL", "GOOG", "SPY", "QQQ", "VOO", "IBIT"):
        exact_result = service.validate(symbol)
        assert exact_result.status is AssetMetadataStatus.OK, (
            f"{symbol} exact: {exact_result.status}: {exact_result.message}"
        )
        assert exact_result.asset is not None
        assert exact_result.asset.canonical_symbol == symbol

    # 使用格式合法但刻意不存在的 symbol，确保请求真正到达 Provider。
    invalid_result = service.validate("Z9Z9Z9Z9Z9")
    assert invalid_result.status is AssetMetadataStatus.NO_MATCH
