from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.models.entities import Employee, EngagementMetric, PerformanceMetric, WorkloadMetric


def _insert_dynamic_workforce(employee_count: int = 8) -> int:
    created = 0
    today = date.today()
    dataset_tag = uuid4().hex[:10]
    with SessionLocal() as db:
        for index in range(employee_count):
            employee = Employee(
                external_id=f"DYN-{dataset_tag}-{index}",
                full_name=f"Dynamic Employee {index}",
                email=f"dynamic-{dataset_tag}-{index}@example.com",
                manager_id=None,
                department="Engineering" if index % 2 == 0 else "Operations",
                role="Engineer",
                location="Remote",
                hire_date=date(2021, 1, 1),
                employment_status="active",
                base_salary=Decimal("1200000"),
            )
            db.add(employee)
            db.flush()

            high_risk = index < max(2, employee_count // 2)
            snapshot_date = today - timedelta(days=index % 4)

            db.add(
                EngagementMetric(
                    employee_id=employee.id,
                    snapshot_date=snapshot_date,
                    engagement_score=0.20 if high_risk else 0.78,
                    sentiment_score=0.18 if high_risk else 0.80,
                )
            )
            db.add(
                WorkloadMetric(
                    employee_id=employee.id,
                    snapshot_date=snapshot_date,
                    overtime_hours=44 if high_risk else 6,
                    meeting_hours=76 if high_risk else 16,
                    after_hours_messages=220 if high_risk else 18,
                )
            )
            db.add(
                PerformanceMetric(
                    employee_id=employee.id,
                    snapshot_date=snapshot_date,
                    performance_rating=0.42 if high_risk else 0.86,
                    goal_completion_pct=0.46 if high_risk else 0.88,
                )
            )
            created += 1

        db.commit()

    return created


def test_snapshot_refresh_and_paginated_risks(client: TestClient) -> None:
    inserted = _insert_dynamic_workforce(employee_count=10)

    refresh = client.post("/api/v1/insights/refresh-risk-snapshots?batch_size=5")
    assert refresh.status_code == 200
    assert refresh.json()["processed_employees"] >= inserted

    page_1 = client.get("/api/v1/insights/risks?limit=3&offset=0")
    page_2 = client.get("/api/v1/insights/risks?limit=3&offset=3")

    assert page_1.status_code == 200
    assert page_2.status_code == 200
    assert len(page_1.json()) <= 3
    assert len(page_2.json()) <= 3

    if page_1.json() and page_2.json():
        assert page_1.json()[0]["employee_id"] != page_2.json()[0]["employee_id"]


def test_nudge_listing_is_paginated(client: TestClient) -> None:
    inserted = _insert_dynamic_workforce(employee_count=6)
    refresh = client.post("/api/v1/insights/refresh-risk-snapshots?batch_size=3")
    assert refresh.status_code == 200
    assert refresh.json()["processed_employees"] >= inserted

    generated = client.post("/api/v1/nudges/generate")
    assert generated.status_code == 200
    assert len(generated.json()) >= 1

    page = client.get("/api/v1/nudges?status=open&limit=1&offset=0")
    assert page.status_code == 200
    assert len(page.json()) <= 1
