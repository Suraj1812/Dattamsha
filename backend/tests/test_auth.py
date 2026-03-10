import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def _login(client: TestClient) -> dict:
    return _login_as(client, "admin@dattamsha.local", "ChangeMe@123")


def _login_as(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_auth_config_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    body = response.json()
    assert "require_authentication" in body
    assert "require_api_key" in body


def test_login_and_me_flow(client: TestClient) -> None:
    login = _login(client)
    assert login["token_type"] == "bearer"
    assert login["user"]["email"] == "admin@dattamsha.local"
    assert login["role"] == "admin"
    assert len(login["permissions"]) > 0

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me.status_code == 200
    body = me.json()
    assert body["is_authenticated"] is True
    assert body["auth_type"] == "token"
    assert body["user"]["email"] == "admin@dattamsha.local"


def test_refresh_and_logout_flow(client: TestClient) -> None:
    login = _login(client)

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["refresh_token"] != login["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed_body["refresh_token"]},
        headers={"Authorization": f"Bearer {refreshed_body['access_token']}"},
    )
    assert logout.status_code == 200
    assert logout.json()["status"] == "ok"


def test_admin_can_create_and_update_user_role(client: TestClient) -> None:
    login = _login(client)
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    unique_email = f"manager-auth-test-{uuid.uuid4().hex[:8]}@example.com"

    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "email": unique_email,
            "full_name": "Manager Auth Test",
            "role": "manager",
            "password": "StrongPass@123",
            "is_active": True,
        },
    )
    assert created.status_code == 200
    user_id = created.json()["id"]
    assert created.json()["role"] == "manager"

    updated = client.patch(
        f"/api/v1/auth/users/{user_id}/role",
        headers=headers,
        json={"role": "analyst"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "analyst"


def test_admin_can_reset_user_password(client: TestClient) -> None:
    login = _login(client)
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    unique_email = f"reset-user-{uuid.uuid4().hex[:8]}@example.com"

    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "email": unique_email,
            "full_name": "Reset User",
            "role": "employee",
            "password": "TempPass@123",
            "is_active": True,
        },
    )
    assert created.status_code == 200
    user_id = created.json()["id"]

    reset = client.post(
        f"/api/v1/auth/users/{user_id}/reset-password",
        headers=headers,
        json={"new_password": "ResetPass@456"},
    )
    assert reset.status_code == 200

    refreshed_login = _login_as(client, unique_email, "ResetPass@456")
    assert refreshed_login["user"]["email"] == unique_email


def test_hr_admin_cannot_manage_auth_users(client: TestClient) -> None:
    admin_login = _login(client)
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    hr_email = f"hr-admin-{uuid.uuid4().hex[:8]}@example.com"

    created_hr = client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={
            "email": hr_email,
            "full_name": "HR Admin Restricted",
            "role": "hr_admin",
            "password": "HrAdminPass@123",
            "is_active": True,
        },
    )
    assert created_hr.status_code == 200

    hr_login = _login_as(client, hr_email, "HrAdminPass@123")
    hr_headers = {"Authorization": f"Bearer {hr_login['access_token']}"}

    create_attempt = client.post(
        "/api/v1/auth/users",
        headers=hr_headers,
        json={
            "email": f"unauthorized-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Unauthorized User",
            "role": "employee",
            "password": "Employee@123",
            "is_active": True,
        },
    )
    assert create_attempt.status_code == 403

    list_attempt = client.get("/api/v1/auth/users", headers=hr_headers)
    assert list_attempt.status_code == 403

def test_auth_required_mode_enforces_login(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATION", "true")
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-auth-secret")

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        denied = client.get("/api/v1/insights/org-health")
        assert denied.status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dattamsha.local", "password": "ChangeMe@123"},
        )
        assert login.status_code == 200

        token = login.json()["access_token"]
        allowed = client.get(
            "/api/v1/insights/org-health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert allowed.status_code == 200

    get_settings.cache_clear()
