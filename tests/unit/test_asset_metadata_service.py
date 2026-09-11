"""Asset Metadata Application Service 测试。"""

from dataclasses import dataclass, field

from position_pilot.application.asset_metadata_service import AssetMetadataService
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetValidationQuery,
    AssetValidationResult,
)


def identity(symbol: str, name: str) -> AssetIdentity:
    """创建测试候选。"""

    return AssetIdentity(symbol, name, "NASDAQ")


@dataclass(slots=True)
class FakeAssetMetadataProvider:
    """记录 Service 传给 Provider 的 provider-neutral 查询。"""

    search_queries: list[AssetSearchQuery] = field(default_factory=list)
    validation_queries: list[AssetValidationQuery] = field(default_factory=list)
    search_result: AssetSearchResult = field(
        default_factory=lambda: AssetSearchResult.success(
            (
                identity("GOOGL", "Alphabet Inc. Class A"),
                identity("GOOG", "Alphabet Inc."),
                identity("MSFT", "Microsoft Corporation"),
            )
        )
    )
    validation_result: AssetValidationResult = field(
        default_factory=lambda: AssetValidationResult.success(identity("GOOG", "Alphabet Inc."))
    )

    def search(self, query: AssetSearchQuery) -> AssetSearchResult:
        self.search_queries.append(query)
        return self.search_result

    def get_exact(self, query: AssetValidationQuery) -> AssetValidationResult:
        self.validation_queries.append(query)
        return self.validation_result


def test_service_forwards_bounded_query_and_sorts_exact_symbol_first() -> None:
    """Service 应统一输入，并将精确 symbol 候选排在前面。"""

    provider = FakeAssetMetadataProvider()
    service = AssetMetadataService(provider)

    result = service.search(" goog ", limit=5)

    assert result.status is AssetMetadataStatus.OK
    assert [candidate.canonical_symbol for candidate in result.candidates] == [
        "GOOG",
        "GOOGL",
        "MSFT",
    ]
    assert provider.search_queries == [AssetSearchQuery("goog", limit=5)]


def test_service_accepts_query_object_and_deduplicates_canonical_symbol() -> None:
    """Query Object 是 provider-neutral Contract，重复候选不应传给 UI。"""

    provider = FakeAssetMetadataProvider(
        search_result=AssetSearchResult.success(
            (
                identity("GOOG", "Alphabet Inc."),
                identity("GOOG", "Alphabet Inc. duplicate"),
            )
        )
    )
    service = AssetMetadataService(provider)

    result = service.search(AssetSearchQuery("alphabet", limit=2))

    assert [candidate.canonical_symbol for candidate in result.candidates] == ["GOOG"]
    assert provider.search_queries == [AssetSearchQuery("alphabet", limit=2)]


def test_service_rejects_invalid_search_without_provider_call() -> None:
    """非法 bounded query 应在 Application 边界失败。"""

    provider = FakeAssetMetadataProvider()
    service = AssetMetadataService(provider)

    result = service.search("", limit=5)

    assert result.status is AssetMetadataStatus.INVALID_REQUEST
    assert provider.search_queries == []


def test_service_exact_validation_normalizes_symbol_and_forwards_failure() -> None:
    """exact validation 只转发 canonical query，并保留 Provider Failure。"""

    provider = FakeAssetMetadataProvider(
        validation_result=AssetValidationResult.failure(
            AssetMetadataStatus.NO_MATCH,
            "没有匹配",
        )
    )
    service = AssetMetadataService(provider)

    result = service.validate(" goog ")

    assert result.status is AssetMetadataStatus.NO_MATCH
    assert provider.validation_queries == [AssetValidationQuery("GOOG")]

    invalid = service.get_exact("not/a/symbol")
    assert invalid.status is AssetMetadataStatus.INVALID_SYMBOL
    assert len(provider.validation_queries) == 1
