"""Asset Metadata Domain Contract 测试。"""

import pytest

from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetStatus,
    AssetValidationQuery,
    AssetValidationResult,
    InvalidAssetMetadata,
)


def asset(symbol: str = "GOOG", name: str = "Alphabet Inc.") -> AssetIdentity:
    """创建用于测试的最小 Asset Identity。"""

    return AssetIdentity(
        canonical_symbol=symbol,
        display_name=name,
        exchange="nasdaq",
        status=AssetStatus.ACTIVE,
    )


def test_asset_identity_normalizes_only_provider_neutral_fields() -> None:
    """Identity 应规范化 symbol/exchange，但不扩展成 Asset Master。"""

    identity = asset(" goog ")

    assert identity.canonical_symbol == "GOOG"
    assert identity.display_name == "Alphabet Inc."
    assert identity.exchange == "NASDAQ"
    assert identity.status is AssetStatus.ACTIVE
    assert not hasattr(identity, "alias")
    assert not hasattr(identity, "fractionable")
    assert not hasattr(identity, "fetched_at")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"canonical_symbol": "not/a/symbol"},
        {"display_name": ""},
        {"exchange": ""},
        {"status": "ACTIVE"},
    ],
)
def test_asset_identity_rejects_invalid_fields(kwargs: dict[str, object]) -> None:
    """Provider-neutral Identity 不能接受格式不确定的字段。"""

    values: dict[str, object] = {
        "canonical_symbol": "GOOG",
        "display_name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "status": AssetStatus.ACTIVE,
    }
    values.update(kwargs)

    with pytest.raises(InvalidAssetMetadata):
        AssetIdentity(**values)  # type: ignore[arg-type]


def test_queries_are_bounded_and_validation_query_is_canonical() -> None:
    """搜索必须有界，exact query 必须先遵守 symbol 格式。"""

    assert AssetSearchQuery("  alphabet  ", limit=3) == AssetSearchQuery("alphabet", limit=3)
    assert AssetValidationQuery(" goog ").symbol == "GOOG"

    with pytest.raises(InvalidAssetMetadata):
        AssetSearchQuery("x" * 101)
    with pytest.raises(InvalidAssetMetadata):
        AssetSearchQuery("GOOG", limit=21)
    with pytest.raises(InvalidAssetMetadata):
        AssetValidationQuery("not/a/symbol")


def test_result_contract_distinguishes_no_match_from_success() -> None:
    """正常无结果不能伪装成成功，也不能携带未经验证 Asset。"""

    success = AssetSearchResult.success((asset(),))
    no_match = AssetSearchResult.failure(AssetMetadataStatus.NO_MATCH, "没有匹配")
    validation = AssetValidationResult.success(asset())

    assert success.status is AssetMetadataStatus.OK
    assert success.candidates == (asset(),)
    assert no_match.candidates == ()
    assert validation.asset == asset()

    with pytest.raises(InvalidAssetMetadata):
        AssetSearchResult(AssetMetadataStatus.OK, (), None)
    with pytest.raises(InvalidAssetMetadata):
        AssetValidationResult(AssetMetadataStatus.NO_MATCH, asset(), "错误")
