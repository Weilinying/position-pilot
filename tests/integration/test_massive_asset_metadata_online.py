"""需要显式凭据与网络授权的 Massive Asset Metadata Smoke Test。"""

import os

import pytest

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.domain.asset_metadata import AssetMetadataStatus
from position_pilot.integrations.massive_asset_metadata import MassiveAssetMetadataProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]


def get_online_service() -> AssetMetadataService:
    """只读取显式导出的进程环境变量，不加载或检查仓库 `.env`。"""

    if os.getenv("RUN_M9_ONLINE_TESTS") != "1":
        pytest.skip("需要 RUN_M9_ONLINE_TESTS=1 才执行 M9 真实 Provider Smoke")
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        pytest.skip("需要显式导出 MASSIVE_API_KEY")
    return AssetMetadataService(
        MassiveAssetMetadataProvider(
            api_key=api_key,
            base_url=os.getenv("MASSIVE_BASE_URL", "https://api.massive.com"),
        )
    )


def test_massive_search_and_exact_validation() -> None:
    """真实 Provider 应支持低频候选搜索与 GOOG canonical validation。"""

    service = get_online_service()

    search_result = service.search("Alphabet", limit=5)
    assert search_result.status is AssetMetadataStatus.OK
    assert any(candidate.canonical_symbol == "GOOG" for candidate in search_result.candidates)

    exact_result = service.validate("goog")
    assert exact_result.status is AssetMetadataStatus.OK
    assert exact_result.asset is not None
    assert exact_result.asset.canonical_symbol == "GOOG"
