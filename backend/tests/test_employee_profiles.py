import uuid

from fastapi.testclient import TestClient


def test_employee_profile_crud_with_base64_avatar(client: TestClient) -> None:
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "external_id": f"EMP-CRUD-{unique_suffix}",
        "full_name": f"Profile CRUD {unique_suffix}",
        "email": f"profile-crud-{unique_suffix}@example.com",
        "manager_id": None,
        "department": "People Operations",
        "role": "HR Specialist",
        "location": "Bengaluru",
        "hire_date": "2024-01-15",
        "employment_status": "active",
        "base_salary": 850000,
        "profile_details": {
            "preferred_name": "PC",
            "phone": "+91 98765 00000",
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_phone": "+91 90000 11111",
            "address": "Koramangala, Bengaluru",
            "date_of_birth": "1993-08-24",
            "skills": "People analytics, communication",
            "bio": "Profile created via automated CRUD test.",
            "avatar_image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
        },
    }

    created = client.post(
        "/api/v1/employees",
        headers={"X-User-Role": "admin"},
        json=payload,
    )
    assert created.status_code == 200
    employee = created.json()
    employee_id = employee["id"]
    assert employee["external_id"] == payload["external_id"]
    assert employee["email"] == payload["email"]

    profile = client.get(
        f"/api/v1/employees/{employee_id}/profile",
        headers={"X-User-Role": "admin"},
    )
    assert profile.status_code == 200
    profile_body = profile.json()
    assert profile_body["employee"]["id"] == employee_id
    assert profile_body["profile_details"]["preferred_name"] == "PC"
    assert profile_body["profile_details"]["avatar_image_base64"].startswith("data:image/png;base64,")

    updated = client.patch(
        f"/api/v1/employees/{employee_id}",
        headers={"X-User-Role": "admin"},
        json={
            "location": "Mumbai",
            "profile_details": {
                "preferred_name": "Updated Name",
                "skills": "People analytics, strategy",
                "avatar_image_base64": "data:image/png;base64,updatedAvatarData",
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["location"] == "Mumbai"

    profile_after_update = client.get(
        f"/api/v1/employees/{employee_id}/profile",
        headers={"X-User-Role": "admin"},
    )
    assert profile_after_update.status_code == 200
    profile_after_update_body = profile_after_update.json()
    assert profile_after_update_body["profile_details"]["preferred_name"] == "Updated Name"
    assert profile_after_update_body["profile_details"]["skills"] == "People analytics, strategy"
    assert profile_after_update_body["profile_details"]["avatar_image_base64"].endswith("updatedAvatarData")

    deleted = client.delete(
        f"/api/v1/employees/{employee_id}",
        headers={"X-User-Role": "admin"},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"status": "deleted", "employee_id": employee_id}

    active_list = client.get(
        f"/api/v1/employees?search={payload['external_id']}",
        headers={"X-User-Role": "admin"},
    )
    assert active_list.status_code == 200
    assert all(row["id"] != employee_id for row in active_list.json())


def test_employee_profile_crud_requires_employees_write_permission(client: TestClient) -> None:
    unique_suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/v1/employees",
        headers={"X-User-Role": "manager"},
        json={
            "external_id": f"EMP-NO-WRITE-{unique_suffix}",
            "full_name": f"No Write {unique_suffix}",
            "email": f"no-write-{unique_suffix}@example.com",
            "manager_id": None,
            "department": "Engineering",
            "role": "Engineer",
            "location": "Pune",
            "hire_date": "2025-01-01",
            "employment_status": "active",
            "base_salary": 1000000,
        },
    )
    assert response.status_code == 403
    assert "Missing permissions" in response.json()["error"]["message"]
