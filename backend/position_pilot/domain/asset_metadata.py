"""Asset Metadata 的 Provider-neutral Domain Contract。"""

from dataclasses import dataclass
from enum import StrEnum

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import normalize_ticker

MAX_ASSET_DISPLAY_NAME_LENGTH = 200
MAX_ASSET_EXCHANGE_LENGTH = 40
MAX_ASSET_SEARCH_QUERY_LENGTH = 100
MIN_ASSET_SEARCH_LIMIT = 1
MAX_ASSET_SEARCH_LIMIT = 20


class InvalidAssetMetadata(ValueError):
    """Asset Metadata 不能满足 Provider-neutral Contract。"""


class AssetMetadataStatus(StrEnum):
    """Asset Metadata Provider 可被 Application 稳定处理的结果状态。"""

    OK = "OK"
    NO_MATCH = "NO_MATCH"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"


def _normalize_nonempty_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise InvalidAssetMetadata(f"{field_name} 必须是字符串")
    normalized = value.strip()
    if not normalized:
        raise InvalidAssetMetadata(f"{field_name} 不能为空")
    if len(normalized) > max_length:
        raise InvalidAssetMetadata(f"{field_name} 最多支持 {max_length} 个字符")
    return normalized


def normalize_asset_symbol(value: str) -> str:
    """复用 Portfolio 的符号格式规则，并转换为 canonical case。"""

    try:
        return normalize_ticker(value)
    except (InvalidPortfolioValue, AttributeError) as error:
        raise InvalidAssetMetadata("canonical_symbol 格式无效") from error


@dataclass(frozen=True, slots=True)
class AssetIdentity:
    """供 Selector 与 Opening State 使用的最小 Asset Identity。

    该对象不保存 Provider-specific Payload，也不代表本地 Asset Master。
    """

    canonical_symbol: str
    display_name: str
    exchange: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "canonical_symbol", normalize_asset_symbol(self.canonical_symbol))
        object.__setattr__(
            self,
            "display_name",
            _normalize_nonempty_text(
                self.display_name,
                field_name="display_name",
                max_length=MAX_ASSET_DISPLAY_NAME_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "exchange",
            _normalize_nonempty_text(
                self.exchange,
                field_name="exchange",
                max_length=MAX_ASSET_EXCHANGE_LENGTH,
            ).upper(),
        )


@dataclass(frozen=True, slots=True)
class AssetSearchQuery:
    """受长度与返回数量限制的 symbol / company name 搜索请求。"""

    query: str
    limit: int = 10

    def __post_init__(self) -> None:
        normalized_query = _normalize_nonempty_text(
            self.query,
            field_name="query",
            max_length=MAX_ASSET_SEARCH_QUERY_LENGTH,
        )
        object.__setattr__(self, "query", normalized_query)
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not MIN_ASSET_SEARCH_LIMIT <= self.limit <= MAX_ASSET_SEARCH_LIMIT
        ):
            raise InvalidAssetMetadata(
                f"limit 必须是 {MIN_ASSET_SEARCH_LIMIT} 到 {MAX_ASSET_SEARCH_LIMIT} 之间的整数"
            )


@dataclass(frozen=True, slots=True)
class AssetValidationQuery:
    """要求 Provider 对单一 canonical symbol 做 exact validation 的请求。"""

    symbol: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_asset_symbol(self.symbol))


@dataclass(frozen=True, slots=True)
class AssetSearchResult:
    """搜索成功候选或明确 Provider Failure 的统一结果。"""

    status: AssetMetadataStatus
    candidates: tuple[AssetIdentity, ...]
    message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssetMetadataStatus):
            raise InvalidAssetMetadata("status 无效")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(candidate, AssetIdentity) for candidate in self.candidates
        ):
            raise InvalidAssetMetadata("candidates 必须是 AssetIdentity tuple")
        if self.status is AssetMetadataStatus.OK:
            if not self.candidates or self.message is not None:
                raise InvalidAssetMetadata(
                    "OK search result 必须包含 candidates 且不能包含 message"
                )
            return
        if self.candidates:
            raise InvalidAssetMetadata("Failure search result 不能包含 candidates")
        if not isinstance(self.message, str) or not self.message.strip():
            raise InvalidAssetMetadata("Failure search result 必须包含 message")

    @classmethod
    def success(cls, candidates: tuple[AssetIdentity, ...]) -> "AssetSearchResult":
        """创建包含至少一个候选的搜索成功结果。"""

        return cls(AssetMetadataStatus.OK, candidates, None)

    @classmethod
    def failure(
        cls,
        status: AssetMetadataStatus,
        message: str,
    ) -> "AssetSearchResult":
        """创建不携带不确定候选的搜索失败结果。"""

        if status is AssetMetadataStatus.OK:
            raise InvalidAssetMetadata("failure 不能使用 OK status")
        return cls(status, (), message)


@dataclass(frozen=True, slots=True)
class AssetValidationResult:
    """exact validation 成功 Asset 或明确 Failure 的统一结果。"""

    status: AssetMetadataStatus
    asset: AssetIdentity | None
    message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssetMetadataStatus):
            raise InvalidAssetMetadata("status 无效")
        if self.status is AssetMetadataStatus.OK:
            if self.asset is None or self.message is not None:
                raise InvalidAssetMetadata("OK validation result 必须包含 asset 且不能包含 message")
            return
        if self.asset is not None:
            raise InvalidAssetMetadata("Failure validation result 不能包含 asset")
        if not isinstance(self.message, str) or not self.message.strip():
            raise InvalidAssetMetadata("Failure validation result 必须包含 message")

    @classmethod
    def success(cls, asset: AssetIdentity) -> "AssetValidationResult":
        """创建 exact validation 成功结果。"""

        return cls(AssetMetadataStatus.OK, asset, None)

    @classmethod
    def failure(
        cls,
        status: AssetMetadataStatus,
        message: str,
    ) -> "AssetValidationResult":
        """创建不携带未经验证 Asset 的失败结果。"""

        if status is AssetMetadataStatus.OK:
            raise InvalidAssetMetadata("failure 不能使用 OK status")
        return cls(status, None, message)
