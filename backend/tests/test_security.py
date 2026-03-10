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


def test_auth_me_returns_role_permissions(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers={"X-User-Role": "manager"})
    assert response.status_code == 200

    body = response.json()
    assert body["role"] == "manager"
    assert "manager.read" in body["permissions"]
    assert "admin" in body["available_roles"]
    assert any(item["role"] == "employee" for item in body["role_permissions"])


def test_rbac_blocks_ingest_for_manager_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ingest/workforce",
        headers={"X-User-Role": "manager"},
        json={
            "source": "rbac-test",
            "employees": [],
            "engagement_metrics": [],
            "workload_metrics": [],
            "performance_metrics": [],
            "collaboration_edges": [],
        },
    )
    assert response.status_code == 403
    assert "Missing permissions" in response.json()["error"]["message"]


def test_rbac_enforces_ingest_read_permissions(client: TestClient) -> None:
    analyst_response = client.get("/api/v1/ingest/runs", headers={"X-User-Role": "analyst"})
    employee_response = client.get("/api/v1/ingest/runs", headers={"X-User-Role": "employee"})

    assert analyst_response.status_code == 200
    assert employee_response.status_code == 403


def test_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATION", "false")
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
