"""Asset Metadata Application Service 与 Provider-neutral Contract。"""

from typing import Protocol

from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchQuery,
    AssetSearchResult,
    AssetValidationQuery,
    AssetValidationResult,
    InvalidAssetMetadata,
)


class AssetMetadataProvider(Protocol):
    """Application 所依赖的最小 Asset Metadata Provider 接口。"""

    def search(self, query: AssetSearchQuery) -> AssetSearchResult: ...

    def get_exact(self, query: AssetValidationQuery) -> AssetValidationResult: ...


class AssetMetadataService:
    """校验 bounded 输入、排序候选并委托单一 Asset Metadata Provider。"""

    def __init__(self, provider: AssetMetadataProvider) -> None:
        self._provider = provider

    def search(self, query: str | AssetSearchQuery, *, limit: int = 10) -> AssetSearchResult:
        """搜索 symbol / company name，并保证候选顺序可重复。"""

        try:
            search_query = (
                query if isinstance(query, AssetSearchQuery) else AssetSearchQuery(query, limit)
            )
        except InvalidAssetMetadata as error:
            return AssetSearchResult.failure(AssetMetadataStatus.INVALID_REQUEST, str(error))

        result = self._provider.search(search_query)
        if result.status is not AssetMetadataStatus.OK:
            return result
        return AssetSearchResult.success(
            self._sort_candidates(search_query.query, result.candidates)
        )

    def get_exact(
        self,
        symbol: str | AssetValidationQuery,
    ) -> AssetValidationResult:
        """对一个候选 symbol 执行 Provider-backed exact validation。"""

        try:
            validation_query = (
                symbol if isinstance(symbol, AssetValidationQuery) else AssetValidationQuery(symbol)
            )
        except InvalidAssetMetadata as error:
            return AssetValidationResult.failure(AssetMetadataStatus.INVALID_SYMBOL, str(error))
        return self._provider.get_exact(validation_query)

    def validate(self, symbol: str | AssetValidationQuery) -> AssetValidationResult:
        """提供语义清晰的 exact validation 别名。"""

        return self.get_exact(symbol)

    @staticmethod
    def _sort_candidates(
        query: str,
        candidates: tuple[AssetIdentity, ...],
    ) -> tuple[AssetIdentity, ...]:
        """将精确 symbol / 名称置前，并去除重复 canonical symbol。"""

        normalized_query = query.strip().casefold()
        unique: dict[str, AssetIdentity] = {}
        for candidate in candidates:
            unique.setdefault(candidate.canonical_symbol, candidate)

        def sort_key(candidate: AssetIdentity) -> tuple[int, str]:
            canonical_symbol = candidate.canonical_symbol.casefold()
            display_name = candidate.display_name.casefold()
            if canonical_symbol == normalized_query:
                rank = 0
            elif display_name == normalized_query:
                rank = 1
            elif canonical_symbol.startswith(normalized_query):
                rank = 2
            else:
                rank = 3
            return rank, canonical_symbol

        return tuple(sorted(unique.values(), key=sort_key))
