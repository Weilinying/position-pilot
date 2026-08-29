"""M7 静态产品界面交付与安全边界测试。"""

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
    assert 'id="portfolio-form"' in page.text
    assert 'id="question-form"' in page.text
    assert 'id="language-toggle"' in page.text
    assert 'data-i18n="context_sources"' in page.text
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
    assert 'source_ticker: "Ticker"' in script
    assert 'source_market_time: "Market time"' in script
    assert 'source_fetched: "Fetched"' in script
    assert 'source_ticker: "标的"' in script
    assert "portfolio_empty_initial" in script
    assert "portfolio_empty_loaded" in script
    assert "toggleLanguage" in script


def test_static_mount_does_not_shadow_existing_routes() -> None:
    """静态资源 Mount 不得遮蔽 Health 与 V1 API。"""

    with TestClient(app) as client:
        health = client.get("/health")
        openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert openapi.status_code == 200
    assert "/v1/portfolios/{user_id}" in openapi.json()["paths"]
    assert "/v1/investment/questions" in openapi.json()["paths"]
