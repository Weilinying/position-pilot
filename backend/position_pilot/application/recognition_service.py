"""Portfolio Opening Import 的 Provider-neutral Recognition Contract。"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from enum import StrEnum
from typing import Protocol, TypeVar

from position_pilot.domain.portfolio import PositionType

MAX_RECOGNITION_TEXT_LENGTH = 20_000
MAX_RECOGNITION_IMAGE_BYTES = 10 * 1024 * 1024
MAX_RECOGNITION_ROWS = 100
MAX_RECOGNITION_WARNINGS = 100
MAX_RECOGNITION_WARNING_LENGTH = 500
MAX_RECOGNITION_SYMBOL_LENGTH = 50
SUPPORTED_RECOGNITION_IMAGE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


class RecognitionInputKind(StrEnum):
    """Recognition 支持的输入形式。"""

    TEXT = "TEXT"
    SCREENSHOT = "SCREENSHOT"


class RecognitionFieldStatus(StrEnum):
    """单个 Draft 字段供 Human Review 使用的状态。"""

    PRESENT = "PRESENT"
    MISSING = "MISSING"
    INVALID = "INVALID"
    AMBIGUOUS = "AMBIGUOUS"


class RecognitionStatus(StrEnum):
    """Recognition Provider 调用的稳定结果状态。"""

    OK = "OK"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DraftField[T]:
    """带 Review 状态的临时识别字段。"""

    value: T | None
    status: RecognitionFieldStatus

    def __post_init__(self) -> None:
        if not isinstance(self.status, RecognitionFieldStatus):
            raise ValueError("Draft field status 无效")
        if self.status is RecognitionFieldStatus.PRESENT and self.value is None:
            raise ValueError("PRESENT Draft field 必须包含 value")
        if self.status is RecognitionFieldStatus.MISSING and self.value is not None:
            raise ValueError("MISSING Draft field 不能包含 value")


@dataclass(frozen=True, slots=True)
class RecognitionInput:
    """只在当前 Request 内使用的文本或图片输入。"""

    kind: RecognitionInputKind
    text: str | None = None
    image_bytes: bytes | None = None
    mime_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RecognitionInputKind):
            raise ValueError("Recognition input kind 无效")
        if self.kind is RecognitionInputKind.TEXT:
            if not isinstance(self.text, str) or not self.text.strip():
                raise ValueError("Text recognition input 不能为空")
            if self.image_bytes is not None or self.mime_type is not None:
                raise ValueError("Text recognition input 不能携带图片字段")
            return
        if not isinstance(self.image_bytes, bytes) or not self.image_bytes:
            raise ValueError("Screenshot recognition input 必须包含图片")
        if not isinstance(self.mime_type, str) or not self.mime_type.strip():
            raise ValueError("Screenshot recognition input 必须包含 MIME type")
        if self.text is not None:
            raise ValueError("Screenshot recognition input 不能携带文本字段")

    @classmethod
    def from_text(cls, text: str) -> "RecognitionInput":
        """创建文本识别输入。"""

        return cls(kind=RecognitionInputKind.TEXT, text=text)

    @classmethod
    def from_screenshot(cls, image_bytes: bytes, *, mime_type: str) -> "RecognitionInput":
        """创建不持久化的截图识别输入。"""

        return cls(
            kind=RecognitionInputKind.SCREENSHOT,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )


@dataclass(frozen=True, slots=True)
class RecognitionDraftRow:
    """单个持仓的可编辑 Recognition Draft 行。"""

    ticker: DraftField[str]
    suggested_symbol: DraftField[str]
    shares: DraftField[Decimal]
    average_cost: DraftField[Decimal]
    position_type: DraftField[PositionType]
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        fields = (
            self.ticker,
            self.suggested_symbol,
            self.shares,
            self.average_cost,
            self.position_type,
        )
        if any(not isinstance(field, DraftField) for field in fields):
            raise ValueError("Recognition Draft row 必须只包含 DraftField")
        if self.confidence is None:
            return
        normalized = _normalize_confidence(self.confidence)
        object.__setattr__(self, "confidence", normalized)


@dataclass(frozen=True, slots=True)
class RecognitionDraft:
    """只用于当前 Browser / Request 生命周期的结构化 Draft。"""

    rows: tuple[RecognitionDraftRow, ...]
    warnings: tuple[str, ...] = ()
    input_kind: RecognitionInputKind | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            raise ValueError("Recognition Draft rows 必须是 tuple")
        if len(self.rows) > MAX_RECOGNITION_ROWS:
            raise ValueError(f"Recognition Draft rows 不得超过 {MAX_RECOGNITION_ROWS}")
        if any(not isinstance(row, RecognitionDraftRow) for row in self.rows):
            raise ValueError("Recognition Draft rows 必须只包含 RecognitionDraftRow")
        if not isinstance(self.warnings, tuple):
            raise ValueError("Recognition Draft warnings 必须是 tuple")
        if len(self.warnings) > MAX_RECOGNITION_WARNINGS:
            raise ValueError("Recognition Draft warnings 数量超过上限")
        if any(
            not isinstance(warning, str)
            or not warning.strip()
            or len(warning.strip()) > MAX_RECOGNITION_WARNING_LENGTH
            for warning in self.warnings
        ):
            raise ValueError("Recognition Draft warning 无效")
        if self.input_kind is not None and not isinstance(self.input_kind, RecognitionInputKind):
            raise ValueError("Recognition Draft input_kind 无效")


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """明确区分临时 Draft 与 Recognition Provider Failure。"""

    status: RecognitionStatus
    draft: RecognitionDraft | None
    message: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, RecognitionStatus):
            raise ValueError("Recognition status 无效")
        if self.status is RecognitionStatus.OK:
            if self.draft is None or self.message is not None:
                raise ValueError("OK Recognition result 必须只包含 draft")
            return
        if self.draft is not None:
            raise ValueError("Failure Recognition result 不能包含 draft")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Failure Recognition result 必须包含安全错误消息")

    @classmethod
    def success(cls, draft: RecognitionDraft) -> "RecognitionResult":
        """创建成功的临时 Draft 结果。"""

        return cls(status=RecognitionStatus.OK, draft=draft, message=None)

    @classmethod
    def failure(cls, status: RecognitionStatus, message: str) -> "RecognitionResult":
        """创建不携带部分 Draft 的失败结果。"""

        if status is RecognitionStatus.OK:
            raise ValueError("failure 不能使用 OK status")
        return cls(status=status, draft=None, message=message)


class RecognitionProvider(Protocol):
    """Application 依赖的最小 Recognition Provider Boundary。"""

    def recognize(self, request: RecognitionInput) -> RecognitionResult: ...


class RecognitionService:
    """校验输入并委托 Recognition Provider，不执行 Agent 或持久化。"""

    def __init__(
        self,
        provider: RecognitionProvider,
        *,
        max_text_length: int = MAX_RECOGNITION_TEXT_LENGTH,
        max_image_bytes: int = MAX_RECOGNITION_IMAGE_BYTES,
    ) -> None:
        if max_text_length < 1 or max_text_length > MAX_RECOGNITION_TEXT_LENGTH:
            raise ValueError("max_text_length 超出允许范围")
        if max_image_bytes < 1 or max_image_bytes > MAX_RECOGNITION_IMAGE_BYTES:
            raise ValueError("max_image_bytes 超出允许范围")
        self._provider = provider
        self._max_text_length = max_text_length
        self._max_image_bytes = max_image_bytes

    def recognize(self, request: RecognitionInput) -> RecognitionResult:
        """验证输入边界后创建临时 Draft。"""

        if not isinstance(request, RecognitionInput):
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Recognition input 无效",
            )
        validation_error = self._validate_request(request)
        if validation_error is not None:
            return RecognitionResult.failure(RecognitionStatus.INVALID_REQUEST, validation_error)
        return self._provider.recognize(request)

    def recognize_text(self, text: str) -> RecognitionResult:
        """识别文本形式的 Opening Import 输入。"""

        if not isinstance(text, str) or not text.strip():
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Recognition text 不能为空",
            )
        if len(text) > self._max_text_length:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Recognition text 超出长度上限",
            )
        try:
            request = RecognitionInput.from_text(text)
        except ValueError:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Recognition text 无效",
            )
        return self._provider.recognize(request)

    def recognize_screenshot(self, image_bytes: bytes, *, mime_type: str) -> RecognitionResult:
        """识别单张截图；图片只在当前调用内存中存在。"""

        if not isinstance(image_bytes, bytes) or not image_bytes:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Screenshot image 不能为空",
            )
        if len(image_bytes) > self._max_image_bytes:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Screenshot image 超出大小上限",
            )
        if not isinstance(mime_type, str) or mime_type.strip().lower() not in {
            mime.lower() for mime in SUPPORTED_RECOGNITION_IMAGE_TYPES
        }:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Screenshot MIME type 不受支持",
            )
        try:
            request = RecognitionInput.from_screenshot(
                image_bytes,
                mime_type=mime_type.strip().lower(),
            )
        except ValueError:
            return RecognitionResult.failure(
                RecognitionStatus.INVALID_REQUEST,
                "Screenshot input 无效",
            )
        return self._provider.recognize(request)

    def _validate_request(self, request: RecognitionInput) -> str | None:
        if request.kind is RecognitionInputKind.TEXT:
            assert request.text is not None
            if len(request.text) > self._max_text_length:
                return "Recognition text 超出长度上限"
            return None
        assert request.image_bytes is not None
        assert request.mime_type is not None
        if len(request.image_bytes) > self._max_image_bytes:
            return "Screenshot image 超出大小上限"
        if request.mime_type.strip().lower() not in {
            mime.lower() for mime in SUPPORTED_RECOGNITION_IMAGE_TYPES
        }:
            return "Screenshot MIME type 不受支持"
        return None


def parse_provider_draft(
    payload: object,
    *,
    input_kind: RecognitionInputKind | None = None,
) -> RecognitionDraft:
    """严格把 Provider Structured JSON 转换为 Provider-neutral Draft。"""

    root = _require_mapping(payload, "Recognition Provider draft")
    _reject_unknown_keys(root, {"rows", "warnings"}, "Recognition Provider draft")
    raw_rows = root.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) > MAX_RECOGNITION_ROWS:
        raise ValueError("Recognition Provider rows 格式无效")
    warnings = _parse_warnings(root.get("warnings", []))
    rows = tuple(_parse_row(raw_row) for raw_row in raw_rows)
    return RecognitionDraft(rows=rows, warnings=warnings, input_kind=input_kind)


def _parse_row(payload: object) -> RecognitionDraftRow:
    row = _require_mapping(payload, "Recognition Provider row")
    allowed_keys = {
        "ticker",
        "suggested_symbol",
        "shares",
        "average_cost",
        "position_type",
        "confidence",
        "statuses",
        "field_status",
    }
    _reject_unknown_keys(row, allowed_keys, "Recognition Provider row")
    if "statuses" in row and "field_status" in row:
        raise ValueError("Recognition Provider row 不能同时包含 statuses 与 field_status")
    raw_statuses = row.get("statuses", row.get("field_status"))
    statuses = _parse_statuses(raw_statuses)

    ticker = _parse_text_field(row.get("ticker"), statuses.get("ticker"), "ticker")
    suggested_symbol = _parse_text_field(
        row.get("suggested_symbol"),
        statuses.get("suggested_symbol"),
        "suggested_symbol",
        uppercase=True,
    )
    shares = _parse_decimal_field(row.get("shares"), statuses.get("shares"), "shares")
    average_cost = _parse_decimal_field(
        row.get("average_cost"),
        statuses.get("average_cost"),
        "average_cost",
    )
    position_type = _parse_position_type_field(
        row.get("position_type"),
        statuses.get("position_type"),
    )
    confidence = _parse_optional_confidence(row.get("confidence"))
    return RecognitionDraftRow(
        ticker=ticker,
        suggested_symbol=suggested_symbol,
        shares=shares,
        average_cost=average_cost,
        position_type=position_type,
        confidence=confidence,
    )


def _parse_statuses(value: object) -> dict[str, RecognitionFieldStatus]:
    if value is None:
        return {}
    statuses = _require_mapping(value, "Recognition Provider statuses")
    field_names = {"ticker", "suggested_symbol", "shares", "average_cost", "position_type"}
    _reject_unknown_keys(statuses, field_names, "Recognition Provider statuses")
    parsed: dict[str, RecognitionFieldStatus] = {}
    for field_name, raw_status in statuses.items():
        if not isinstance(raw_status, str):
            raise ValueError("Recognition Provider field status 必须是字符串")
        try:
            parsed[field_name] = RecognitionFieldStatus(raw_status.strip().upper())
        except ValueError as error:
            raise ValueError("Recognition Provider field status 无效") from error
    return parsed


def _parse_text_field(
    value: object,
    explicit_status: RecognitionFieldStatus | None,
    field_name: str,
    *,
    uppercase: bool = False,
) -> DraftField[str]:
    if value is None:
        status = explicit_status or RecognitionFieldStatus.MISSING
        if status is RecognitionFieldStatus.PRESENT:
            raise ValueError(f"{field_name} PRESENT 但缺少 value")
        return DraftField(value=None, status=status)
    if not isinstance(value, str):
        if explicit_status is not RecognitionFieldStatus.INVALID:
            raise ValueError(f"{field_name} value 格式无效")
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_RECOGNITION_SYMBOL_LENGTH:
        if explicit_status in {RecognitionFieldStatus.INVALID, RecognitionFieldStatus.AMBIGUOUS}:
            return DraftField(value=None, status=explicit_status)
        if explicit_status is not None:
            raise ValueError(f"{field_name} status 与 value 冲突")
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    if explicit_status is RecognitionFieldStatus.MISSING:
        raise ValueError(f"{field_name} MISSING 但包含 value")
    if explicit_status is RecognitionFieldStatus.INVALID:
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    if explicit_status is RecognitionFieldStatus.PRESENT or explicit_status is None:
        return DraftField(
            value=normalized.upper() if uppercase else normalized,
            status=explicit_status or RecognitionFieldStatus.PRESENT,
        )
    return DraftField(value=normalized, status=explicit_status)


def _parse_decimal_field(
    value: object,
    explicit_status: RecognitionFieldStatus | None,
    field_name: str,
) -> DraftField[Decimal]:
    if value is None:
        status = explicit_status or RecognitionFieldStatus.MISSING
        if status is RecognitionFieldStatus.PRESENT:
            raise ValueError(f"{field_name} PRESENT 但缺少 value")
        return DraftField(value=None, status=status)
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        if explicit_status is RecognitionFieldStatus.INVALID:
            return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
        raise ValueError(f"{field_name} value 格式无效")
    try:
        normalized = Decimal(str(value).strip()) if isinstance(value, str) else Decimal(str(value))
    except (DecimalException, ValueError):
        if explicit_status is RecognitionFieldStatus.INVALID:
            return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
        raise ValueError(f"{field_name} value 不是有效 Decimal") from None
    if not normalized.is_finite() or normalized <= 0:
        if explicit_status in {RecognitionFieldStatus.INVALID, RecognitionFieldStatus.AMBIGUOUS}:
            return DraftField(value=None, status=explicit_status)
        if explicit_status is not None:
            raise ValueError(f"{field_name} status 与 value 冲突")
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    if explicit_status is RecognitionFieldStatus.MISSING:
        raise ValueError(f"{field_name} MISSING 但包含 value")
    if explicit_status is RecognitionFieldStatus.INVALID:
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    return DraftField(
        value=normalized,
        status=explicit_status or RecognitionFieldStatus.PRESENT,
    )


def _parse_position_type_field(
    value: object,
    explicit_status: RecognitionFieldStatus | None,
) -> DraftField[PositionType]:
    if value is None:
        status = explicit_status or RecognitionFieldStatus.MISSING
        if status is RecognitionFieldStatus.PRESENT:
            raise ValueError("position_type PRESENT 但缺少 value")
        return DraftField(value=None, status=status)
    if not isinstance(value, str):
        if explicit_status is RecognitionFieldStatus.INVALID:
            return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
        raise ValueError("position_type value 格式无效")
    try:
        normalized = PositionType(value.strip().upper())
    except ValueError:
        if explicit_status is RecognitionFieldStatus.INVALID:
            return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
        if explicit_status is RecognitionFieldStatus.AMBIGUOUS:
            return DraftField(value=None, status=RecognitionFieldStatus.AMBIGUOUS)
        if explicit_status is not None:
            raise ValueError("position_type status 与 value 冲突") from None
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    if explicit_status is RecognitionFieldStatus.MISSING:
        raise ValueError("position_type MISSING 但包含 value")
    if explicit_status is RecognitionFieldStatus.INVALID:
        return DraftField(value=None, status=RecognitionFieldStatus.INVALID)
    return DraftField(value=normalized, status=explicit_status or RecognitionFieldStatus.PRESENT)


def _parse_optional_confidence(value: object) -> Decimal | None:
    if value is None:
        return None
    return _normalize_confidence(value)


def _normalize_confidence(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("confidence 必须是 0 到 1 之间的数值")
    try:
        normalized = Decimal(str(value).strip()) if isinstance(value, str) else Decimal(str(value))
    except (DecimalException, ValueError):
        raise ValueError("confidence 必须是 0 到 1 之间的数值") from None
    if not normalized.is_finite() or normalized < 0 or normalized > 1:
        raise ValueError("confidence 必须是 0 到 1 之间的数值")
    return normalized


def _parse_warnings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_RECOGNITION_WARNINGS:
        raise ValueError("Recognition Provider warnings 格式无效")
    normalized: list[str] = []
    for warning in value:
        if not isinstance(warning, str):
            raise ValueError("Recognition Provider warning 必须是字符串")
        text = warning.strip()
        if not text or len(text) > MAX_RECOGNITION_WARNING_LENGTH:
            raise ValueError("Recognition Provider warning 长度无效")
        normalized.append(text)
    return tuple(normalized)


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} 必须是 JSON object")
    return value


def _reject_unknown_keys(
    value: Mapping[str, object],
    allowed: set[str],
    field_name: str,
) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        raise ValueError(f"{field_name} 包含未知字段")


__all__ = [
    "DraftField",
    "MAX_RECOGNITION_IMAGE_BYTES",
    "MAX_RECOGNITION_ROWS",
    "MAX_RECOGNITION_TEXT_LENGTH",
    "RecognitionDraft",
    "RecognitionDraftRow",
    "RecognitionFieldStatus",
    "RecognitionInput",
    "RecognitionInputKind",
    "RecognitionProvider",
    "RecognitionResult",
    "RecognitionService",
    "RecognitionStatus",
    "SUPPORTED_RECOGNITION_IMAGE_TYPES",
    "parse_provider_draft",
]
