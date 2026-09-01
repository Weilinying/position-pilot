"""Recognition Application Contract 测试。"""

from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from position_pilot.application.recognition_service import (
    DraftField,
    RecognitionDraft,
    RecognitionDraftRow,
    RecognitionFieldStatus,
    RecognitionInput,
    RecognitionInputKind,
    RecognitionResult,
    RecognitionService,
    RecognitionStatus,
    parse_provider_draft,
)
from position_pilot.domain.portfolio import PositionType


def draft_row(
    *,
    ticker: str | None = "ADBE",
    suggested_symbol: str | None = "ADBE",
    shares: Decimal | None = Decimal("0.2"),
    average_cost: Decimal | None = None,
    average_cost_status: RecognitionFieldStatus | None = None,
    confidence: Decimal | None = Decimal("0.97"),
) -> RecognitionDraftRow:
    """创建用于测试的最小 Draft 行。"""

    return RecognitionDraftRow(
        ticker=DraftField(
            ticker,
            RecognitionFieldStatus.PRESENT
            if ticker is not None
            else RecognitionFieldStatus.MISSING,
        ),
        suggested_symbol=DraftField(
            suggested_symbol,
            RecognitionFieldStatus.PRESENT
            if suggested_symbol is not None
            else RecognitionFieldStatus.MISSING,
        ),
        shares=DraftField(
            shares,
            RecognitionFieldStatus.PRESENT
            if shares is not None
            else RecognitionFieldStatus.MISSING,
        ),
        average_cost=DraftField(
            average_cost,
            average_cost_status
            or (
                RecognitionFieldStatus.PRESENT
                if average_cost is not None
                else RecognitionFieldStatus.MISSING
            ),
        ),
        position_type=DraftField(None, RecognitionFieldStatus.MISSING),
        confidence=confidence,
    )


@dataclass(slots=True)
class FakeRecognitionProvider:
    """不访问网络、数据库或 InvestmentAgent 的固定 Provider。"""

    result: RecognitionResult
    requests: list[RecognitionInput] = field(default_factory=list)

    def recognize(self, request: RecognitionInput) -> RecognitionResult:
        self.requests.append(request)
        return self.result


def test_text_recognition_only_delegates_a_temporary_draft() -> None:
    """Application 只委托输入并返回 Draft，不具备任何写入能力。"""

    draft = RecognitionDraft(
        rows=(draft_row(),),
        input_kind=RecognitionInputKind.TEXT,
    )
    provider = FakeRecognitionProvider(RecognitionResult.success(draft))
    service = RecognitionService(provider)

    result = service.recognize_text("ADBE 0.2 shares")

    assert result.status is RecognitionStatus.OK
    assert result.draft is draft
    assert provider.requests == [RecognitionInput.from_text("ADBE 0.2 shares")]
    assert not hasattr(result.draft, "user_id")
    assert not hasattr(result.draft, "provider_payload")


def test_ibkr_like_missing_average_cost_is_preserved_without_inference() -> None:
    """截图缺少 average cost 时必须保留 MISSING，不能从其他字段推算。"""

    payload = {
        "rows": [
            {
                "ticker": "ADBE",
                "suggested_symbol": "ADBE",
                "shares": "0.2",
                "average_cost": None,
                "position_type": None,
                "confidence": 0.99,
                "statuses": {
                    "ticker": "PRESENT",
                    "suggested_symbol": "PRESENT",
                    "shares": "PRESENT",
                    "average_cost": "MISSING",
                    "position_type": "MISSING",
                },
            }
        ],
        "warnings": ["截图未显示平均成本"],
    }

    draft = parse_provider_draft(payload, input_kind=RecognitionInputKind.SCREENSHOT)
    row = draft.rows[0]

    assert row.shares.value == Decimal("0.2")
    assert row.average_cost.value is None
    assert row.average_cost.status is RecognitionFieldStatus.MISSING
    assert row.confidence == Decimal("0.99")


def test_confidence_is_only_a_review_signal() -> None:
    """高 Confidence 不能让缺失字段变成可写入字段。"""

    payload = {
        "rows": [
            {
                "ticker": "ADBE",
                "suggested_symbol": "ADBE",
                "shares": "0.2",
                "average_cost": None,
                "position_type": None,
                "confidence": 1,
            }
        ],
        "warnings": [],
    }

    row = parse_provider_draft(payload).rows[0]

    assert row.confidence == Decimal("1")
    assert row.average_cost.status is RecognitionFieldStatus.MISSING


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("recognize_text", ""),
        ("recognize_text", "x" * 20_001),
    ],
)
def test_invalid_text_does_not_call_provider(method: str, value: str) -> None:
    """Text Boundary Failure 不得消耗 Provider 调用。"""

    provider = FakeRecognitionProvider(RecognitionResult.success(RecognitionDraft(rows=())))
    service = RecognitionService(provider)

    result = getattr(service, method)(value)

    assert result.status is RecognitionStatus.INVALID_REQUEST
    assert provider.requests == []


def test_invalid_screenshot_mime_and_size_do_not_call_provider() -> None:
    """不支持的 MIME 与超大图片必须在 Application Boundary 被拒绝。"""

    provider = FakeRecognitionProvider(RecognitionResult.success(RecognitionDraft(rows=())))
    service = RecognitionService(provider, max_image_bytes=3)

    invalid_mime = service.recognize_screenshot(b"x", mime_type="text/plain")
    oversized = service.recognize_screenshot(b"xxxx", mime_type="image/jpeg")

    assert invalid_mime.status is RecognitionStatus.INVALID_REQUEST
    assert oversized.status is RecognitionStatus.INVALID_REQUEST
    assert provider.requests == []


def test_provider_draft_rejects_unknown_fields_and_invalid_status_combinations() -> None:
    """Provider JSON 超出 Contract 或与字段状态冲突时必须失败。"""

    with pytest.raises(ValueError):
        parse_provider_draft(
            {
                "rows": [{"ticker": "ADBE", "unexpected": "instruction"}],
                "warnings": [],
            }
        )
    with pytest.raises(ValueError):
        parse_provider_draft(
            {
                "rows": [
                    {
                        "ticker": None,
                        "statuses": {"ticker": "PRESENT"},
                    }
                ],
                "warnings": [],
            }
        )


def test_ambiguous_symbol_remains_reviewable_data() -> None:
    """AMBIGUOUS 只标记人工复核，不自动选择或验证 canonical symbol。"""

    draft = parse_provider_draft(
        {
            "rows": [
                {
                    "ticker": "GOOG/GOOGL",
                    "suggested_symbol": "GOOG",
                    "shares": "1",
                    "average_cost": "100",
                    "position_type": None,
                    "confidence": 0.4,
                    "statuses": {
                        "ticker": "AMBIGUOUS",
                        "suggested_symbol": "AMBIGUOUS",
                        "shares": "PRESENT",
                        "average_cost": "PRESENT",
                        "position_type": "MISSING",
                    },
                }
            ],
            "warnings": [],
        }
    )

    row = draft.rows[0]
    assert row.ticker.status is RecognitionFieldStatus.AMBIGUOUS
    assert row.suggested_symbol.status is RecognitionFieldStatus.AMBIGUOUS
    assert row.suggested_symbol.value == "GOOG"
    assert row.position_type.value is None
    assert PositionType.UNSPECIFIED not in {row.position_type.value}
