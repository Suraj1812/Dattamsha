from fastapi.testclient import TestClient


def test_hiring_simulation(client: TestClient) -> None:
    payload = {
        "planned_hires": 10,
        "avg_salary": 1200000,
        "expected_revenue_per_hire": 2400000,
        "expected_time_to_productivity_months": 3,
    }
    response = client.post("/api/v1/simulations/hiring-impact", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["annual_hiring_cost"] > 0
    assert "payback_months" in body
