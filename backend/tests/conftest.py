import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture()
def secure_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("ENABLE_DOCS", "true")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
