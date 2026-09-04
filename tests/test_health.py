"""验证有意不依赖外部服务的 API 基线。"""

from fastapi.testclient import TestClient

from opspilot.main import create_app


def test_process_health_contains_only_process_metadata() -> None:
    response = TestClient(create_app()).get("/api/v1/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "application": "OpsPilot API",
        "status": "ok",
        "version": "0.1.0",
    }


def test_no_business_routes_are_exposed() -> None:
    response = TestClient(create_app()).get("/api/v1/incidents")

    assert response.status_code == 404
