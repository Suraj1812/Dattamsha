from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_protected_endpoints_require_api_key(secure_client: TestClient) -> None:
    response = secure_client.get("/api/v1/insights/org-health")
    assert response.status_code == 401


def test_protected_endpoints_accept_valid_api_key(secure_client: TestClient) -> None:
    response = secure_client.get(
        "/api/v1/insights/org-health",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200


def test_invalid_api_key_rejected(secure_client: TestClient) -> None:
    response = secure_client.get(
        "/api/v1/insights/org-health",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")

    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        payload = {"question": "leave policy"}
        first = client.post("/api/v1/assistant/policy-query", json=payload)
        second = client.post("/api/v1/assistant/policy-query", json=payload)
        third = client.post("/api/v1/assistant/policy-query", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["type"] == "rate_limit"

    get_settings.cache_clear()
