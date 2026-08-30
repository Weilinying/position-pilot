"""M8 本地 Portfolio 管理界面与安全边界测试。"""

from fastapi.testclient import TestClient

from position_pilot.main import app


def test_serves_product_interface_and_static_assets() -> None:
    """同源页面与资源应可访问且不影响 API 进程。"""

    with TestClient(app) as client:
        page = client.get("/app/")
        script = client.get("/static/app.js")
        stylesheet = client.get("/static/styles.css")

    assert page.status_code == 200
    assert "PositionPilot · Decision Desk" in page.text
    assert 'id="create-form"' in page.text
    assert 'id="portfolio-form"' in page.text
    assert 'id="forget-pointer-button"' in page.text
    assert 'id="trade-form"' in page.text
    assert 'id="cash-form"' in page.text
    assert 'id="question-form"' in page.text
    assert 'id="language-toggle"' in page.text
    assert 'data-i18n="context_sources"' in page.text
    assert 'id="onboarding-view"' in page.text
    assert 'id="app-shell"' in page.text
    assert 'id="chat-view"' in page.text
    assert 'id="portfolio-view"' in page.text
    assert 'id="session-list"' in page.text
    assert 'id="conversation-list"' in page.text
    assert 'id="assistant-response-template"' in page.text
    assert 'id="portfolio-tab-overview"' in page.text
    assert 'id="portfolio-tab-trade"' in page.text
    assert 'id="portfolio-tab-cash"' in page.text
    assert 'id="initial-cash"' in page.text
    assert 'value="0"' in page.text
    assert 'id="opening-form"' in page.text
    assert 'id="opening-draft-rows"' in page.text
    assert 'id="opening-record-list"' in page.text
    assert 'id="transaction-list"' in page.text
    assert 'id="cash-event-list"' in page.text
    assert '<option value="" data-i18n="unspecified">' in page.text
    assert 'data-i18n-placeholder="shares_placeholder"' in page.text
    assert script.status_code == 200
    assert stylesheet.status_code == 200


def test_client_script_preserves_identity_and_safe_text_boundary() -> None:
    """静态 Contract 应保留 User 身份代次并禁止动态 HTML 注入入口。"""

    with TestClient(app) as client:
        script = client.get("/static/app.js").text

    assert "loadedUserId" in script
    assert "portfolioGeneration" in script
    assert "questionGeneration" in script
    assert ".textContent" in script
    assert "innerHTML" not in script
    assert "outerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script
    assert 'source_ticker: "Ticker"' in script
    assert 'source_market_time: "Market time"' in script
    assert 'source_fetched: "Fetched"' in script
    assert 'source_ticker: "标的"' in script
    assert "portfolio_empty_initial" in script
    assert "portfolio_empty_loaded" in script
    assert "toggleLanguage" in script
    assert "createQuestionExchange" in script
    assert "questionHistoryCount" in script
    assert script.count("window.localStorage.setItem(") == 1
    assert "DECIMAL_INPUT_PATTERN" in script
    assert "showFieldError" in script
    assert 'shares_required: "Enter shares.' in script
    assert 'shares_required: "请填写股数。' in script
    assert 'INSUFFICIENT_CASH: "api_insufficient_cash"' in script


def test_client_script_preserves_m8_write_and_recovery_boundaries() -> None:
    """M8 静态 Contract 应保留恢复指针、写锁与后端时间语义。"""

    with TestClient(app) as client:
        script = client.get("/static/app.js").text

    assert 'LOCAL_POINTER_KEY = "positionpilot.local-portfolio.v1"' in script
    assert "window.localStorage" in script
    assert 'writeState: "idle"' in script
    assert "writeGeneration" not in script
    assert 'clientState.writeState === "submitting"' in script
    assert "preserveRecoveryPointer" in script
    assert "response.status === 404 && !preserveRecoveryPointer" in script
    assert 'fetch("/v1/portfolios"' in script
    assert "/transactions`" in script
    assert "/cash-events`" in script
    assert '"openingPositions", "opening-positions"' in script
    assert "isOpeningPositionsWritePayload" in script
    assert "firstPosition.id" in script
    assert "payload.position_type = elements.tradePositionType.value" in script
    assert "payload.occurred_at = occurredAt.value" in script
    assert "new Date(rawValue)" in script
    assert "Number(elements.tradePrice" not in script
    assert "Number(elements.cashAmount" not in script


def test_static_mount_does_not_shadow_existing_routes() -> None:
    """静态资源 Mount 不得遮蔽 Health 与 V1 API。"""

    with TestClient(app) as client:
        health = client.get("/health")
        openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert openapi.status_code == 200
    assert "/v1/portfolios/{user_id}" in openapi.json()["paths"]
    assert "/v1/investment/questions" in openapi.json()["paths"]
