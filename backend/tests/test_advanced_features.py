from fastapi.testclient import TestClient


def _workforce_payload(tag: str) -> dict:
    return {
        "source": "api-test",
        "employees": [
            {
                "external_id": f"MGR-{tag}",
                "full_name": f"Dynamic Manager {tag}",
                "email": f"manager-{tag}@example.com",
                "manager_external_id": None,
                "department": "Engineering",
                "role": "Engineering Manager",
                "location": "Bengaluru",
                "hire_date": "2021-01-15",
                "employment_status": "active",
                "base_salary": 2500000,
            },
            {
                "external_id": f"IC-{tag}",
                "full_name": f"Dynamic IC {tag}",
                "email": f"ic-{tag}@example.com",
                "manager_external_id": f"MGR-{tag}",
                "department": "Engineering",
                "role": "Senior Engineer",
                "location": "Bengaluru",
                "hire_date": "2022-03-01",
                "employment_status": "active",
                "base_salary": 1800000,
            },
        ],
        "engagement_metrics": [
            {
                "external_id": f"MGR-{tag}",
                "snapshot_date": "2026-03-01",
                "engagement_score": 0.75,
                "sentiment_score": 0.72,
            },
            {
                "external_id": f"IC-{tag}",
                "snapshot_date": "2026-03-01",
                "engagement_score": 0.22,
                "sentiment_score": 0.21,
            },
        ],
        "workload_metrics": [
            {
                "external_id": f"MGR-{tag}",
                "snapshot_date": "2026-03-01",
                "overtime_hours": 8,
                "meeting_hours": 22,
                "after_hours_messages": 20,
            },
            {
                "external_id": f"IC-{tag}",
                "snapshot_date": "2026-03-01",
                "overtime_hours": 44,
                "meeting_hours": 76,
                "after_hours_messages": 220,
            },
        ],
        "performance_metrics": [
            {
                "external_id": f"MGR-{tag}",
                "snapshot_date": "2026-03-01",
                "performance_rating": 0.84,
                "goal_completion_pct": 0.82,
            },
            {
                "external_id": f"IC-{tag}",
                "snapshot_date": "2026-03-01",
                "performance_rating": 0.41,
                "goal_completion_pct": 0.45,
            },
        ],
        "collaboration_edges": [
            {
                "source_external_id": f"MGR-{tag}",
                "target_external_id": f"IC-{tag}",
                "interaction_count": 12,
            }
        ],
    }


def test_dynamic_ingest_and_analytics_endpoints(client: TestClient) -> None:
    payload = _workforce_payload("A1")
    ingest = client.post("/api/v1/ingest/workforce", json=payload)
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["employees_upserted"] == 2
    assert body["metrics_upserted"] == 6
    assert body["edges_upserted"] == 1

    runs = client.get("/api/v1/ingest/runs?limit=5")
    assert runs.status_code == 200
    assert len(runs.json()) >= 1

    trends = client.get("/api/v1/insights/trends?days=180")
    assert trends.status_code == 200
    assert isinstance(trends.json(), list)

    cohorts = client.get("/api/v1/insights/cohorts?dimension=department")
    anomalies = client.get("/api/v1/insights/anomalies?dimension=department&min_population=1")
    finance = client.get("/api/v1/analytics/workforce-finance")

    assert cohorts.status_code == 200
    assert anomalies.status_code == 200
    assert finance.status_code == 200
    assert finance.json()["annual_payroll"] >= 0

    employees = client.get("/api/v1/employees?search=Dynamic%20Manager%20A1")
    assert employees.status_code == 200
    assert len(employees.json()) >= 1
    manager_id = employees.json()[0]["id"]

    manager_view = client.get(f"/api/v1/managers/{manager_id}/team-overview")
    assert manager_view.status_code == 200
    assert manager_view.json()["team_size"] >= 1


def test_nudge_dispatch_and_feedback_endpoints(client: TestClient) -> None:
    payload = _workforce_payload("B1")
    ingest = client.post("/api/v1/ingest/workforce", json=payload)
    assert ingest.status_code == 200

    generated = client.post("/api/v1/nudges/generate")
    assert generated.status_code == 200

    nudges = client.get("/api/v1/nudges?status=open&limit=10")
    assert nudges.status_code == 200
    assert len(nudges.json()) >= 1
    nudge_id = nudges.json()[0]["id"]

    dispatch = client.post(
        "/api/v1/nudges/dispatch",
        json={"channel": "console", "max_items": 5, "include_resolved": False},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["attempted"] >= 1

    dispatch_logs = client.get(f"/api/v1/nudges/{nudge_id}/dispatches")
    assert dispatch_logs.status_code == 200

    feedback_create = client.post(
        f"/api/v1/nudges/{nudge_id}/feedback",
        json={
            "manager_identifier": "mgr-b1",
            "action_taken": "Conducted stay interview and adjusted workload split",
            "effectiveness_rating": 4,
            "notes": "Employee agreed on action plan",
        },
    )
    assert feedback_create.status_code == 200

    feedback_list = client.get(f"/api/v1/nudges/{nudge_id}/feedback")
    assert feedback_list.status_code == 200
    assert len(feedback_list.json()) >= 1


def test_compliance_consent_and_audit_endpoints(client: TestClient) -> None:
    payload = _workforce_payload("C1")
    ingest = client.post("/api/v1/ingest/workforce", json=payload)
    assert ingest.status_code == 200

    employee_search = client.get("/api/v1/employees?search=Dynamic%20IC%20C1")
    assert employee_search.status_code == 200
    assert len(employee_search.json()) == 1
    employee_id = employee_search.json()[0]["id"]

    consent_create = client.post(
        f"/api/v1/employees/{employee_id}/consents",
        json={
            "consent_type": "nudge_engine",
            "status": "granted",
            "source": "self-service",
            "details": "Accepted in portal",
        },
    )
    assert consent_create.status_code == 200
    assert consent_create.json()["consent_type"] == "nudge_engine"
    assert consent_create.json()["status"] == "granted"

    consent_list = client.get(f"/api/v1/employees/{employee_id}/consents?status=granted")
    assert consent_list.status_code == 200
    assert len(consent_list.json()) >= 1

    audit_events = client.get("/api/v1/compliance/audit-events?action=consent.upsert")
    assert audit_events.status_code == 200
    assert len(audit_events.json()) >= 1
