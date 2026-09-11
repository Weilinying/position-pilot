"""M9 Asset Search 与 Recognition Import API Contract 测试。"""

import base64
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import Account, SetupPortfolioCommand
from position_pilot.application.portfolio_service import InitializeOpeningPositionsCommand
from position_pilot.application.recognition_service import (
    DraftField,
    RecognitionDraft,
    RecognitionDraftRow,
    RecognitionFieldStatus,
    RecognitionInput,
    RecognitionInputKind,
    RecognitionResult,
)
from position_pilot.domain.asset_metadata import (
    AssetIdentity,
    AssetMetadataStatus,
    AssetSearchResult,
    AssetValidationResult,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    OpeningPosition,
    PortfolioState,
    User,
)
from position_pilot.main import (
    app,
    get_asset_metadata_service_dependency,
    get_current_account_dependency,
    get_portfolio_service_dependency,
    get_recognition_service_dependency,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")
NOW = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)


def make_account(*, portfolio_user_id: UUID | None = None) -> Account:
    """创建不经过真实 Session / Database 的已认证 Account。"""

    return Account(
        id=ACCOUNT_ID,
        email="import@example.com",
        display_name="Import User",
        password_hash="not-returned",
        portfolio_user_id=portfolio_user_id,
        created_at=NOW,
    )


def make_draft() -> RecognitionDraft:
    """创建包含所有字段的最小 Structured Draft。"""

    return RecognitionDraft(
        rows=(
            RecognitionDraftRow(
                ticker=DraftField("ADBE", RecognitionFieldStatus.PRESENT),
                suggested_symbol=DraftField("ADBE", RecognitionFieldStatus.PRESENT),
                shares=DraftField(Decimal("0.2"), RecognitionFieldStatus.PRESENT),
                average_cost=DraftField(None, RecognitionFieldStatus.MISSING),
                position_type=DraftField(None, RecognitionFieldStatus.MISSING),
                confidence=Decimal("0.87"),
            ),
        ),
        warnings=("average cost 未在截图中显示",),
        input_kind=RecognitionInputKind.SCREENSHOT,
    )


@dataclass(slots=True)
class FakeAssetMetadataService:
    """返回固定 Provider-neutral Asset Search Result。"""

    result: AssetSearchResult
    queries: list[tuple[str, int]] = field(default_factory=list)

    def search(self, query: str, *, limit: int = 10) -> AssetSearchResult:
        self.queries.append((query, limit))
        return self.result


@dataclass(slots=True)
class FakeAssetValidator:
    """记录 Recognition 自动解析使用的 exact validation。"""

    results: dict[str, AssetValidationResult] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)

    def get_exact(self, symbol: str) -> AssetValidationResult:
        self.queries.append(symbol)
        return self.results.get(
            symbol,
            AssetValidationResult.failure(AssetMetadataStatus.NO_MATCH, "没有匹配 Asset"),
        )

    def validate(self, symbol: str) -> AssetValidationResult:
        """复用相同结果支持显式 exact-validation API。"""

        return self.get_exact(symbol)


@dataclass(slots=True)
class FakeRecognitionService:
    """记录临时 Recognition 输入，不访问真实 Provider。"""

    result: RecognitionResult
    text_inputs: list[str] = field(default_factory=list)
    screenshot_inputs: list[RecognitionInput] = field(default_factory=list)

    def recognize_text(self, text: str) -> RecognitionResult:
        self.text_inputs.append(text)
        return self.result

    def recognize_screenshot(self, image_bytes: bytes, *, mime_type: str) -> RecognitionResult:
        self.screenshot_inputs.append(
            RecognitionInput.from_screenshot(image_bytes, mime_type=mime_type)
        )
        return self.result


@dataclass(slots=True)
class FakePortfolioReader:
    """提供 Opening Import sealed-state 预检查所需的只读查询。"""

    opening_positions: tuple[OpeningPosition, ...] = ()
    transactions: tuple[object, ...] = ()
    cash_events: tuple[object, ...] = ()
    reconciliations: tuple[object, ...] = ()
    queried: list[str] = field(default_factory=list)

    def list_opening_positions(self, user_id: UUID) -> tuple[OpeningPosition, ...]:
        del user_id
        self.queried.append("opening")
        return self.opening_positions

    def list_transactions(self, user_id: UUID) -> tuple[object, ...]:
        del user_id
        self.queried.append("transactions")
        return self.transactions

    def list_cash_events(self, user_id: UUID) -> tuple[object, ...]:
        del user_id
        self.queried.append("cash")
        return self.cash_events

    def list_position_reconciliations(self, user_id: UUID) -> tuple[object, ...]:
        del user_id
        self.queried.append("reconciliations")
        return self.reconciliations

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        del user_id
        return PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(
                user_id=USER_ID,
                initial_cash=Decimal("1000"),
                available_cash=Decimal("1000"),
            ),
            positions=(),
            transaction_count=0,
        )


@dataclass(slots=True)
class FakeOpeningImportService:
    """记录已确认 Opening Position 写入命令。"""

    result: tuple[OpeningPosition, ...] | User | Exception
    setup_commands: list[SetupPortfolioCommand] = field(default_factory=list)
    initialize_commands: list[InitializeOpeningPositionsCommand] = field(default_factory=list)

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        self.setup_commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        if not isinstance(self.result, User):
            raise AssertionError("Fake setup result 必须是 User")
        return self.result

    def initialize_opening_positions(
        self,
        command: InitializeOpeningPositionsCommand,
    ) -> tuple[OpeningPosition, ...]:
        self.initialize_commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        if not isinstance(self.result, tuple):
            raise AssertionError("Fake initialize result 必须是 tuple")
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个 Test 使用独立 Dependency Override。"""

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_account(*, portfolio_user_id: UUID | None = None) -> None:
    """替换当前 Account，避免读取真实 Session。"""

    app.dependency_overrides[get_current_account_dependency] = lambda: make_account(
        portfolio_user_id=portfolio_user_id
    )
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: FakeAssetValidator()


def test_asset_search_allows_account_without_portfolio(client: TestClient) -> None:
    """Asset Search 只需要认证，不要求先创建 Portfolio。"""

    override_account()
    result = AssetSearchResult.success((AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ"),))
    service = FakeAssetMetadataService(result)
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: service

    response = client.get("/v1/assets/search", params={"query": "adobe", "limit": 5})

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "candidates": [
            {
                "canonical_symbol": "ADBE",
                "display_name": "Adobe Inc.",
                "exchange": "NASDAQ",
            }
        ],
        "message": None,
    }
    assert service.queries == [("adobe", 5)]


def test_asset_validation_distinguishes_valid_invalid_and_provider_failure(
    client: TestClient,
) -> None:
    """只有 Provider 明确无匹配时才返回 INVALID。"""

    override_account()
    validator = FakeAssetValidator(
        {
            "ADBE": AssetValidationResult.success(AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ")),
            "NONE": AssetValidationResult.failure(
                AssetMetadataStatus.NO_MATCH,
                "Provider 明确没有匹配 Asset",
            ),
            "LATER": AssetValidationResult.failure(
                AssetMetadataStatus.RATE_LIMITED,
                "Provider rate limited",
            ),
        }
    )
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: validator

    valid = client.get("/v1/assets/validate", params={"symbol": "ADBE"})
    invalid = client.get("/v1/assets/validate", params={"symbol": "NONE"})
    unavailable = client.get("/v1/assets/validate", params={"symbol": "LATER"})

    assert valid.json() == {
        "status": "VALID",
        "candidate": {
            "canonical_symbol": "ADBE",
            "display_name": "Adobe Inc.",
            "exchange": "NASDAQ",
        },
        "message": None,
        "provider_status": "OK",
    }
    assert invalid.json()["status"] == "INVALID"
    assert invalid.json()["provider_status"] == "NO_MATCH"
    assert unavailable.json()["status"] == "PROVIDER_UNAVAILABLE"
    assert unavailable.json()["provider_status"] == "RATE_LIMITED"


def test_text_recognition_returns_reviewable_draft_without_portfolio(
    client: TestClient,
) -> None:
    """未 Setup Account 也能生成只读 Draft，并完整序列化字段状态和值。"""

    override_account()
    recognition = FakeRecognitionService(RecognitionResult.success(make_draft()))
    asset_validator = FakeAssetValidator(
        {"ADBE": AssetValidationResult.success(AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ"))}
    )
    portfolio = FakePortfolioReader()
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_validator
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio

    response = client.post(
        "/v1/portfolio/import/recognize-text",
        json={"text": "ADBE 0.2 shares"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "draft": {
            "rows": [
                {
                    "ticker": {"value": "ADBE", "status": "PRESENT"},
                    "suggested_symbol": {"value": "ADBE", "status": "PRESENT"},
                    "shares": {"value": "0.2", "status": "PRESENT"},
                    "average_cost": {"value": None, "status": "MISSING"},
                    "position_type": {"value": None, "status": "MISSING"},
                    "confidence": "0.87",
                    "asset_resolution": {
                        "status": "OK",
                        "candidate": {
                            "canonical_symbol": "ADBE",
                            "display_name": "Adobe Inc.",
                            "exchange": "NASDAQ",
                        },
                    },
                }
            ],
            "warnings": ["average cost 未在截图中显示"],
            "input_kind": "SCREENSHOT",
        },
        "message": None,
    }
    assert recognition.text_inputs == ["ADBE 0.2 shares"]
    assert asset_validator.queries == ["ADBE"]
    assert portfolio.queried == []


def test_recognition_asset_resolution_failure_keeps_editable_draft(
    client: TestClient,
) -> None:
    """Asset 自动解析失败不能丢弃 Recognition Draft 或伪造选择。"""

    override_account()
    recognition = FakeRecognitionService(RecognitionResult.success(make_draft()))
    asset_validator = FakeAssetValidator(
        {
            "ADBE": AssetValidationResult.failure(
                AssetMetadataStatus.RATE_LIMITED,
                "Provider rate limited",
            )
        }
    )
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_validator
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: FakePortfolioReader()

    response = client.post(
        "/v1/portfolio/import/recognize-text",
        json={"text": "ADBE 0.2 shares"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["draft"]["rows"][0]["suggested_symbol"] == {
        "value": "ADBE",
        "status": "PRESENT",
    }
    assert payload["draft"]["rows"][0]["asset_resolution"] == {
        "status": "RATE_LIMITED",
        "candidate": None,
    }


def test_recognition_validates_present_ticker_when_suggested_symbol_is_missing(
    client: TestClient,
) -> None:
    """Vision 只返回明确 ticker 时仍应完成 exact validation。"""

    override_account()
    draft = make_draft()
    row = draft.rows[0]
    recognition = FakeRecognitionService(
        RecognitionResult.success(
            RecognitionDraft(
                rows=(
                    RecognitionDraftRow(
                        ticker=row.ticker,
                        suggested_symbol=DraftField(None, RecognitionFieldStatus.MISSING),
                        shares=row.shares,
                        average_cost=row.average_cost,
                        position_type=row.position_type,
                        confidence=row.confidence,
                    ),
                ),
                input_kind=RecognitionInputKind.SCREENSHOT,
            )
        )
    )
    asset_validator = FakeAssetValidator(
        {"ADBE": AssetValidationResult.success(AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ"))}
    )
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_validator
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: FakePortfolioReader()

    response = client.post(
        "/v1/portfolio/import/recognize-screenshot",
        json={
            "mime_type": "image/jpeg",
            "image_base64": base64.b64encode(b"broker-image").decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert asset_validator.queries == ["ADBE"]
    assert response.json()["draft"]["rows"][0]["asset_resolution"] == {
        "status": "OK",
        "candidate": {
            "canonical_symbol": "ADBE",
            "display_name": "Adobe Inc.",
            "exchange": "NASDAQ",
        },
    }


def test_recognition_only_resolves_present_symbols_and_deduplicates_validation(
    client: TestClient,
) -> None:
    """同一 Draft 的重复 symbol 只验证一次，歧义字段不自动绑定。"""

    override_account()
    present_row = make_draft().rows[0]
    ambiguous_row = RecognitionDraftRow(
        ticker=DraftField("GOOG/GOOGL", RecognitionFieldStatus.AMBIGUOUS),
        suggested_symbol=DraftField("GOOG", RecognitionFieldStatus.PRESENT),
        shares=DraftField(Decimal("1"), RecognitionFieldStatus.PRESENT),
        average_cost=DraftField(Decimal("100"), RecognitionFieldStatus.PRESENT),
        position_type=DraftField(None, RecognitionFieldStatus.MISSING),
        confidence=Decimal("0.5"),
    )
    recognition = FakeRecognitionService(
        RecognitionResult.success(
            RecognitionDraft(
                rows=(present_row, present_row, ambiguous_row),
                input_kind=RecognitionInputKind.TEXT,
            )
        )
    )
    asset_validator = FakeAssetValidator(
        {"ADBE": AssetValidationResult.success(AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ"))}
    )
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_validator
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: FakePortfolioReader()

    response = client.post(
        "/v1/portfolio/import/recognize-text",
        json={"text": "three rows"},
    )

    rows = response.json()["draft"]["rows"]
    assert asset_validator.queries == ["ADBE"]
    assert rows[0]["asset_resolution"]["status"] == "OK"
    assert rows[1]["asset_resolution"]["status"] == "OK"
    assert rows[2]["asset_resolution"] is None


def test_screenshot_recognition_strictly_decodes_base64_and_keeps_bytes_in_memory(
    client: TestClient,
) -> None:
    """Screenshot API 只向 Application 传递严格解码后的 bytes。"""

    override_account()
    recognition = FakeRecognitionService(RecognitionResult.success(make_draft()))
    asset_validator = FakeAssetValidator(
        {"ADBE": AssetValidationResult.success(AssetIdentity("ADBE", "Adobe Inc.", "NASDAQ"))}
    )
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_asset_metadata_service_dependency] = lambda: asset_validator
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: FakePortfolioReader()

    response = client.post(
        "/v1/portfolio/import/recognize-screenshot",
        json={
            "mime_type": "image/jpeg",
            "image_base64": base64.b64encode(b"ibkr-image").decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert len(recognition.screenshot_inputs) == 1
    assert recognition.screenshot_inputs[0].image_bytes == b"ibkr-image"
    assert asset_validator.queries == ["ADBE"]

    invalid = client.post(
        "/v1/portfolio/import/recognize-screenshot",
        json={"mime_type": "image/jpeg", "image_base64": "not base64!"},
    )
    assert invalid.status_code == 200
    assert invalid.json() == {
        "status": "INVALID_REQUEST",
        "draft": None,
        "message": "image_base64 必须是有效的 Base64",
    }
    assert len(recognition.screenshot_inputs) == 1
    assert asset_validator.queries == ["ADBE"]


def test_recognition_rejects_sealed_portfolio_before_provider_call(client: TestClient) -> None:
    """Opening State 已封闭时必须在 Recognition Provider 之前拒绝。"""

    opening = OpeningPosition.create(
        opening_position_id=UUID("00000000-0000-0000-0000-000000000004"),
        user_id=USER_ID,
        ticker="ADBE",
        shares=Decimal("1"),
        average_cost=Decimal("100"),
        recorded_at=NOW,
    )
    override_account(portfolio_user_id=USER_ID)
    recognition = FakeRecognitionService(RecognitionResult.success(make_draft()))
    portfolio = FakePortfolioReader(opening_positions=(opening,))
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio

    response = client.post(
        "/v1/portfolio/import/recognize-text",
        json={"text": "ADBE 1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OPENING_STATE_SEALED"
    assert recognition.text_inputs == []
    assert portfolio.queried == ["opening"]


def test_screenshot_recognition_remains_available_for_existing_portfolio(
    client: TestClient,
) -> None:
    """已有 Portfolio 可生成 Reconciliation Draft，不受 Opening Gate 限制。"""

    opening = OpeningPosition.create(
        opening_position_id=UUID("00000000-0000-0000-0000-000000000004"),
        user_id=USER_ID,
        ticker="ADBE",
        shares=Decimal("1"),
        average_cost=Decimal("100"),
        recorded_at=NOW,
    )
    override_account(portfolio_user_id=USER_ID)
    recognition = FakeRecognitionService(RecognitionResult.success(make_draft()))
    portfolio = FakePortfolioReader(opening_positions=(opening,))
    app.dependency_overrides[get_recognition_service_dependency] = lambda: recognition
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio

    response = client.post(
        "/v1/portfolio/import/recognize-screenshot",
        json={
            "mime_type": "image/png",
            "image_base64": base64.b64encode(b"current-portfolio").decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert recognition.screenshot_inputs[0].image_bytes == b"current-portfolio"
    assert portfolio.queried == []
