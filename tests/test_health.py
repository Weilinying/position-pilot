"""应用存活检查测试。"""

from fastapi.testclient import TestClient

from position_pilot.main import app


def test_health_returns_stable_liveness_response() -> None:
    """存活检查应在不依赖数据库时返回稳定响应。"""

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
