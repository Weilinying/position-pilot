"""M8 Authentication、首次使用与单一 Portfolio 界面 Contract 测试。"""

from fastapi.testclient import TestClient

from position_pilot.main import app


def _product_assets() -> tuple[str, str, str]:
    """读取同源页面与静态资源，供静态 Contract 测试复用。"""

    with TestClient(app) as client:
        page = client.get("/app/")
        script = client.get("/static/app.js")
        stylesheet = client.get("/static/styles.css")

    assert page.status_code == 200
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    return page.text, script.text, stylesheet.text


def test_serves_public_auth_setup_and_authenticated_app_shell() -> None:
    """页面应把主页、认证、Portfolio Setup 与登录后工作区分成独立 View。"""

    page, script, stylesheet = _product_assets()

    assert "PositionPilot · Decision Desk" in page
    for element_id in (
        "home-view",
        "engineering-smoke-banner",
        "auth-view",
        "setup-view",
        "app-shell",
        "home-register-button",
        "home-login-button",
        "hero-register-button",
        "hero-login-button",
        "register-form",
        "login-form",
        "setup-form",
        "setup-initial-cash",
        "setup-draft-rows",
        "setup-zero-button",
        "setup-submit",
        "nav-chat",
        "nav-portfolio",
        "session-list",
        "conversation-list",
        "account-display-name",
        "account-email",
        "header-account-name",
        "account-message",
        "logout-button",
        "header-logout-button",
        "question-form",
        "portfolio-view",
        "open-buy-dialog",
        "open-import-dialog",
        "open-cash-dialog",
        "position-list",
        "trade-dialog",
        "cash-dialog",
        "import-dialog",
        "buy-correction-dialog",
        "transaction-detail-dialog",
        "transaction-list",
        "cash-event-list",
    ):
        assert f'id="{element_id}"' in page

    assert 'autocomplete="new-password"' in page
    assert 'autocomplete="current-password"' in page
    assert 'id="setup-initial-cash"' in page
    assert 'value="0"' in page
    assert 'id="create-form"' not in page
    assert 'id="portfolio-form"' not in page
    assert 'id="user-id"' not in page
    assert "localStorage" not in script
    assert "source-disclosure" in page
    assert "source-disclosure" in stylesheet
    assert 'get("engineering_smoke")' in script


def test_attachment_composer_and_reconciliation_contract() -> None:
    """截图附件只在用户点击识别后上传，并支持复核后校准已有持仓。"""

    page, script, stylesheet = _product_assets()

    for prefix in ("setup", "reconciliation"):
        for element_id in (
            f"{prefix}-attachment-composer",
            f"{prefix}-attachment-dropzone",
            f"{prefix}-attachment-preview",
            f"{prefix}-import-screenshot-submit",
        ):
            assert f'id="{element_id}"' in page
        assert f'id="{prefix}-attachment-choose"' not in page
    for element_id in (
        "position-reconciliation",
        "reconciliation-form",
        "reconciliation-broker",
        "reconciliation-revalidate",
        "reconciliation-submit",
        "reconciliation-add-row",
        "reconciliation-load-current",
    ):
        assert f'id="{element_id}"' in page

    for marker in (
        "data-attachment-composer",
        "data-attachment-dropzone",
        "stageAttachments",
        "openImagePreview",
        'id="image-preview-dialog"',
        "attachment-preview-open",
        "pastedImageFile",
        "event.clipboardData",
        "dragover",
        "dataTransfer?.files",
        "attachments: []",
        "readFileAsDataUrl(attachment.file, task.controller.signal)",
        "MAX_IMPORT_IMAGES = 2",
        "combinedDraft.rows.push",
        "start_recognition",
        "revalidateReconciliationAssets",
        "validateUnboundDraftAssets",
        "canonical === ticker",
        "canonical === visibleTicker",
        "requestJson(`/v1/assets/validate?${params.toString()}`",
        'url: "/v1/portfolio/reconciliations"',
        "source: state.reconciliationSource",
        "target_shares",
        "target_average_cost",
        "optionalPositionType",
    ):
        assert marker in script or marker in page
    assert ".attachment-preview-card" in stylesheet
    assert ".image-preview-dialog" in stylesheet
    assert page.count('data-attachment-dropzone role="button" tabindex="0"') == 2
    assert 'event.key !== "Enter" && event.key !== " "' in script
    assert page.count('type="file" accept="image/jpeg,image/png,image/webp" multiple') == 3
    assert 'aria-labelledby="reconciliation-import-title"' in page
    revalidation = script[
        script.index("async function revalidateReconciliationAssets") : script.index(
            "async function handleReconciliation"
        )
    ]
    assert "delete row.dataset.assetSymbol" not in revalidation
    assert 'error.code === "INVALID_ASSET_SYMBOL"' in script

    assert ".attachment-dropzone" in stylesheet
    assert ".attachment-preview" in stylesheet
    assert ".reconciliation-card" in stylesheet
    assert ".holding-row" in stylesheet
    assert ".trade-lot-row" in stylesheet
    assert "loadCurrentReconciliationDraft" in script
    assert "collectSellAllocations" in script


def test_client_script_preserves_session_identity_safe_text_and_question_boundary() -> None:
    """前端应使用 Session-derived identity、安全 DOM 和独立 question 请求。"""

    page, script, _ = _product_assets()

    for marker in (
        "account: null",
        "authGeneration",
        "loadedUserId",
        "portfolioGeneration",
        "portfolioReadState",
        "authTransition",
        "questionGeneration",
        'requestJson("/v1/auth/session")',
        'requestJson("/v1/auth/register"',
        'requestJson("/v1/auth/login"',
        'requestJson("/v1/auth/logout"',
        'requestJson("/v1/investment/questions"',
        "body: JSON.stringify({ question })",
        "questionPending",
        'state.writeState !== "refresh_required"',
        'HTTP_500: "unexpected_server_error"',
        'FUTURE_TIMESTAMP: "future_time"',
        'INVALID_TRANSACTION: "invalid_transaction"',
        'INVALID_CASH_EVENT: "invalid_cash_event"',
        'PORTFOLIO_ALREADY_EXISTS: "portfolio_already_exists"',
        'state.portfolioReadState = "loading"',
        "refreshPortfolio({ afterMutation: true })",
        'state.authTransition = "logging_out"',
        'state.authTransition = "restoring"',
        'state.authTransition = "session_error"',
        'setMessage(messageElement, "logout_failed")',
        "state.portfolioController?.abort()",
        "state.questionController?.abort()",
        "setAuthNavigationDisabled(true)",
        "capturedUserId",
        ".textContent",
        "createOpeningRow",
        "position_type",
    ):
        assert marker in script

    for code, label in {
        "AUTHENTICATION_REQUIRED": "session_expired",
        "PORTFOLIO_SETUP_REQUIRED": "setup_required",
        "PORTFOLIO_NOT_FOUND": "portfolio_unavailable",
        "USER_NOT_FOUND": "portfolio_unavailable",
        "INVALID_CREDENTIALS": "invalid_credentials",
        "EMAIL_ALREADY_REGISTERED": "email_registered",
        "INVALID_ACCOUNT": "invalid_account",
        "PORTFOLIO_ALREADY_EXISTS": "portfolio_already_exists",
        "INVALID_PORTFOLIO": "invalid_portfolio",
        "INVALID_OPENING_STATE": "invalid_opening_state",
        "INVALID_TRANSACTION": "invalid_transaction",
        "INVALID_CASH_EVENT": "invalid_cash_event",
        "VALIDATION_ERROR": "invalid_form",
        "INSUFFICIENT_CASH": "insufficient_cash",
        "INSUFFICIENT_SHARES": "insufficient_shares",
        "OPENING_STATE_SEALED": "opening_sealed",
        "FUTURE_TIMESTAMP": "future_time",
    }.items():
        assert f'{code}: "{label}"' in script
        assert script.count(f"{label}:") >= 2

    assert 'ERROR_LABELS[error.code] ?? "unexpected_server_error"' in script
    assert "20260911-portfolio-compact-2" in page

    assert "innerHTML" not in script
    assert "outerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script
    assert "LOCAL_POINTER" not in script
    assert "localStorage" not in script
    assert "JSON.stringify({ user_id" not in script
    assert (
        "error.message"
        not in script[
            script.index("function apiMessageKey") : script.index("function formatDecimal")
        ]
    )
    assert "/v1/portfolios/" not in script
    assert "/v1/portfolio/opening-positions" in script
    assert "/v1/portfolio/reconciliations" in script
    assert "/v1/portfolio/transactions" in script
    assert "/v1/portfolio/cash-events" in script
    assert "/v1/portfolio/valuation" in script
    assert "/v1/portfolio/buy-corrections" in script
    assert "/classification`" in script
    assert "/correction`" in script


def test_opening_import_review_contract_is_provider_neutral_and_explicit() -> None:
    """Opening Import 应只生成可编辑 Draft，并沿用现有 Save 完成用户确认。"""

    page, script, stylesheet = _product_assets()

    for prefix in ("setup", "opening"):
        for element_id in (
            f"{prefix}-import-tools",
            f"{prefix}-import-text-tab",
            f"{prefix}-import-screenshot-tab",
            f"{prefix}-import-text",
            f"{prefix}-import-text-submit",
            f"{prefix}-import-screenshot",
            f"{prefix}-import-screenshot-submit",
            f"{prefix}-import-draft-feedback",
        ):
            assert f'id="{element_id}"' in page
        for removed_id in (
            f"{prefix}-import-manual-tab",
            f"{prefix}-asset-query",
            f"{prefix}-asset-search",
            f"{prefix}-asset-candidates",
        ):
            assert f'id="{removed_id}"' not in page

    for endpoint in (
        "/v1/assets/search",
        "/v1/portfolio/import/recognize-text",
        "/v1/portfolio/import/recognize-screenshot",
    ):
        assert endpoint in script
    for marker in (
        "canonical_symbol",
        "display_name",
        "exchange",
        "suggested_symbol",
        "average_cost",
        "confidence",
        "FileReader",
        "image_base64",
        "state.importController?.abort()",
        "state.importGeneration",
        "state.importPending",
        "row.dataset.assetSymbol",
        "rowData.asset_resolution",
        "applySelectedAsset(row, resolution.candidate)",
        "clearSelectedAsset(row)",
        "asset_selection_required",
        "asset_auto_selected",
        "readFileAsDataUrl(attachment.file, task.controller.signal)",
        "renderRecognitionDraft(config, { draft: combinedDraft }",
        "recognition_draft_ready",
        "screenshot_privacy_notice",
        "MAX_IMPORT_IMAGES = 2",
        "controls.attachments",
        "stageAttachments(config",
        "for (const attachment of attachments)",
        "combinedDraft.rows.push",
        "validateUnboundDraftAssets",
        "canonical === ticker",
        "bindAssetAutocomplete",
        "ASSET_AUTOCOMPLETE_DELAY_MS",
        'event.key === "ArrowDown"',
        'event.key === "Escape"',
        "current.generation !== generation",
    ):
        assert marker in script or marker in page

    assert 'accept="image/jpeg,image/png,image/webp"' in page
    assert "multiple" in page
    assert "Alibaba Model Studio" in page
    assert "PositionPilot does not save" in page
    assert "Provider's fixed retention period is not publicly disclosed" in page
    assert "innerHTML" not in script
    assert "localStorage" not in script
    assert "row.dataset.assetSymbol !== normalizedTicker" in script
    assert "data-review-status" in stylesheet
    assert "draft-row-review" in stylesheet
    assert ".asset-autocomplete-list" in stylesheet
    assert ".asset-autocomplete-option" in stylesheet


def test_question_composer_keyboard_contract() -> None:
    """Ask Composer 应复用标准表单提交，并保护换行、输入法与重复提交边界。"""

    page, script, _ = _product_assets()

    assert 'id="question-form"' in page
    assert 'id="question-hint"' in page
    assert "Enter to ask · Shift+Enter for a new line." in page
    for marker in (
        "questionComposing: false",
        'addEventListener("compositionstart"',
        'addEventListener("compositionend"',
        'addEventListener("keydown", handleQuestionKeydown)',
        'event.key !== "Enter"',
        "event.shiftKey",
        "state.questionComposing",
        "event.isComposing",
        "event.keyCode === 229",
        "event.repeat",
        "state.questionPending",
        "elements.questionForm.requestSubmit()",
    ):
        assert marker in script
    assert "event.preventDefault(); return;" in script


def test_portfolio_uses_compact_tables_and_dialog_actions() -> None:
    """Portfolio 主界面应聚焦当前持仓与紧凑历史，并把录入收进 Dialog。"""

    page, script, stylesheet = _product_assets()
    portfolio = page[page.index('id="portfolio-view"') : page.index("</main>")]

    for marker in (
        'class="holdings-table-header"',
        'class="history-table-header"',
        'id="open-buy-dialog"',
        'id="open-import-dialog"',
        'id="open-cash-dialog"',
        'id="trade-dialog"',
        'id="cash-dialog"',
        'id="import-dialog"',
        'id="transaction-detail-dialog"',
        'id="trade-fee"',
        'data-i18n="average_cost_fee_included"',
    ):
        assert marker in page
    for removed_copy in (
        "Review deterministic state",
        "Appends an immutable record",
        "Session-owned",
        "Ledger-derived",
        "Reconcile from a broker screenshot",
        "Fee is calculated automatically.",
    ):
        assert removed_copy not in portfolio
    for marker in (
        "openTradeDialog",
        "setTradeAction",
        "createHistoryRow",
        "openTransactionDetail",
        "effectiveTransaction",
        "transactionFeeText",
        'payload.fee = fee',
        "currentNote && freshNote",
        "freshNote.cloneNode(true)",
        'elements.tradeBuyMode.addEventListener("click"',
        'elements.tradeSellMode.addEventListener("click"',
        'url: "/v1/portfolio/reconciliations"',
    ):
        assert marker in script
    for selector in (
        ".compact-portfolio",
        ".portfolio-product-header",
        ".history-row",
        ".product-dialog",
        ".holding-disclosure",
    ):
        assert selector in stylesheet
    assert "createRecordCard" not in script


def test_sources_are_details_closed_by_default() -> None:
    """Source disclosure 应默认关闭，并由现有回答 View 独立控制。"""

    page, script, stylesheet = _product_assets()
    start = page.index('<details class="source-disclosure">')
    end = page.index("</details>", start)
    details_template = page[start:end]

    assert "<summary>" in details_template
    assert 'class="source-count"' in details_template
    assert 'class="source-list"' in details_template
    assert 'class="source-disclosure" open' not in details_template
    assert "view.details.open = false" in script
    assert ".source-disclosure:not([open])" in stylesheet


def test_static_mount_and_v1_authenticated_route_contract() -> None:
    """同源静态 Mount 不得遮蔽 Health、Auth、单一 Portfolio 与 Agent 路由。"""

    with TestClient(app) as client:
        health = client.get("/health")
        openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]

    for path in (
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/logout",
        "/v1/auth/session",
        "/v1/portfolio",
        "/v1/portfolio/opening-positions",
        "/v1/portfolio/reconciliations",
        "/v1/portfolio/transactions",
        "/v1/portfolio/valuation",
        "/v1/portfolio/lots/{lot_id}/classification",
        "/v1/portfolio/lots/{lot_id}/correction",
        "/v1/portfolio/buy-corrections",
        "/v1/portfolio/cash-events",
        "/v1/investment/questions",
    ):
        assert path in paths

    assert "/v1/portfolios/{user_id}" in paths
    assert "user_id" not in paths["/v1/investment/questions"]["post"]["requestBody"]
