from fastapi.testclient import TestClient


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_and_readiness(client: TestClient) -> None:
    live = client.get("/api/v1/health/live")
    ready = client.get("/api/v1/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "alive"}

    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_request_id_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
