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
        "portfolio-tab-overview",
        "portfolio-tab-trade",
        "portfolio-tab-cash",
        "opening-record-list",
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
    assert "20260901-m9-import-1" in page

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
    assert "/v1/portfolio/transactions" in script
    assert "/v1/portfolio/cash-events" in script


def test_opening_import_review_contract_is_provider_neutral_and_explicit() -> None:
    """Opening Import 应只生成可编辑 Draft，并沿用现有 Save 完成用户确认。"""

    page, script, stylesheet = _product_assets()

    for prefix in ("setup", "opening"):
        for element_id in (
            f"{prefix}-import-tools",
            f"{prefix}-import-manual-tab",
            f"{prefix}-import-text-tab",
            f"{prefix}-import-screenshot-tab",
            f"{prefix}-asset-query",
            f"{prefix}-asset-search",
            f"{prefix}-asset-candidates",
            f"{prefix}-import-text",
            f"{prefix}-import-text-submit",
            f"{prefix}-import-screenshot",
            f"{prefix}-import-screenshot-submit",
            f"{prefix}-import-draft-feedback",
        ):
            assert f'id="{element_id}"' in page

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
        "config.rows.contains(config.pendingRow)",
        "readFileAsDataUrl(file, task.controller.signal)",
        "if (renderRecognitionDraft(config, payload",
        "recognition_draft_ready",
        "screenshot_privacy_notice",
    ):
        assert marker in script or marker in page

    assert 'accept="image/jpeg,image/png,image/webp"' in page
    assert "Alibaba Model Studio" in page
    assert "PositionPilot does not save" in page
    assert "Provider's fixed retention period is not publicly disclosed" in page
    assert "innerHTML" not in script
    assert "localStorage" not in script
    assert "data-review-status" in stylesheet
    assert "draft-row-review" in stylesheet


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
        "/v1/portfolio/transactions",
        "/v1/portfolio/cash-events",
        "/v1/investment/questions",
    ):
        assert path in paths

    assert "/v1/portfolios/{user_id}" in paths
    assert "user_id" not in paths["/v1/investment/questions"]["post"]["requestBody"]
