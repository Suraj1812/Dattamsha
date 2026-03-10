from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.entities import (
    CollaborationEdge,
    Employee,
    EngagementMetric,
    PerformanceMetric,
    WorkloadMetric,
)
from app.schemas.hr import IngestResponse


SAMPLE_DIR = Path("samples")


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


def load_sample_data(db: Session, source: str = "sample") -> IngestResponse:
    if source != "sample":
        raise ValueError("Only 'sample' source is implemented in MVP")

    employees_loaded = _load_employees(db, SAMPLE_DIR / "employees.csv")
    metrics_loaded = 0
    metrics_loaded += _load_engagement(db, SAMPLE_DIR / "engagement_metrics.csv")
    metrics_loaded += _load_workload(db, SAMPLE_DIR / "workload_metrics.csv")
    metrics_loaded += _load_performance(db, SAMPLE_DIR / "performance_metrics.csv")
    metrics_loaded += _load_collaboration(db, SAMPLE_DIR / "collaboration_edges.csv")

    db.commit()
    return IngestResponse(source=source, employees_loaded=employees_loaded, metrics_loaded=metrics_loaded)


def _load_employees(db: Session, path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            existing = db.query(Employee).filter(Employee.external_id == row["external_id"]).first()
            if existing:
                existing.full_name = row["full_name"]
                existing.email = row["email"]
                existing.department = row["department"]
                existing.role = row["role"]
                existing.location = row["location"]
                existing.employment_status = row["employment_status"]
                existing.base_salary = Decimal(row["base_salary"])
                existing.hire_date = _parse_date(row["hire_date"])
            else:
                db.add(
                    Employee(
                        external_id=row["external_id"],
                        full_name=row["full_name"],
                        email=row["email"],
                        department=row["department"],
                        role=row["role"],
                        location=row["location"],
                        employment_status=row["employment_status"],
                        base_salary=Decimal(row["base_salary"]),
                        hire_date=_parse_date(row["hire_date"]),
                    )
                )
            count += 1

    db.flush()
    # Second pass to resolve manager references by external_id.
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            manager_external_id = row.get("manager_external_id")
            if not manager_external_id:
                continue
            employee = db.query(Employee).filter(Employee.external_id == row["external_id"]).first()
            manager = db.query(Employee).filter(Employee.external_id == manager_external_id).first()
            if employee and manager:
                employee.manager_id = manager.id

    return count


def _load_engagement(db: Session, path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            employee = db.query(Employee).filter(Employee.external_id == row["external_id"]).first()
            if not employee:
                continue
            snapshot_date = _parse_date(row["snapshot_date"])
            existing = (
                db.query(EngagementMetric)
                .filter(
                    EngagementMetric.employee_id == employee.id,
                    EngagementMetric.snapshot_date == snapshot_date,
                )
                .first()
            )
            if existing:
                existing.engagement_score = float(row["engagement_score"])
                existing.sentiment_score = float(row["sentiment_score"])
            else:
                db.add(
                    EngagementMetric(
                        employee_id=employee.id,
                        snapshot_date=snapshot_date,
                        engagement_score=float(row["engagement_score"]),
                        sentiment_score=float(row["sentiment_score"]),
                    )
                )
            count += 1
    return count


def _load_workload(db: Session, path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            employee = db.query(Employee).filter(Employee.external_id == row["external_id"]).first()
            if not employee:
                continue
            snapshot_date = _parse_date(row["snapshot_date"])
            existing = (
                db.query(WorkloadMetric)
                .filter(
                    WorkloadMetric.employee_id == employee.id,
                    WorkloadMetric.snapshot_date == snapshot_date,
                )
                .first()
            )
            if existing:
                existing.overtime_hours = float(row["overtime_hours"])
                existing.meeting_hours = float(row["meeting_hours"])
                existing.after_hours_messages = int(row["after_hours_messages"])
            else:
                db.add(
                    WorkloadMetric(
                        employee_id=employee.id,
                        snapshot_date=snapshot_date,
                        overtime_hours=float(row["overtime_hours"]),
                        meeting_hours=float(row["meeting_hours"]),
                        after_hours_messages=int(row["after_hours_messages"]),
                    )
                )
            count += 1
    return count


def _load_performance(db: Session, path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            employee = db.query(Employee).filter(Employee.external_id == row["external_id"]).first()
            if not employee:
                continue
            snapshot_date = _parse_date(row["snapshot_date"])
            existing = (
                db.query(PerformanceMetric)
                .filter(
                    PerformanceMetric.employee_id == employee.id,
                    PerformanceMetric.snapshot_date == snapshot_date,
                )
                .first()
            )
            if existing:
                existing.performance_rating = float(row["performance_rating"])
                existing.goal_completion_pct = float(row["goal_completion_pct"])
            else:
                db.add(
                    PerformanceMetric(
                        employee_id=employee.id,
                        snapshot_date=snapshot_date,
                        performance_rating=float(row["performance_rating"]),
                        goal_completion_pct=float(row["goal_completion_pct"]),
                    )
                )
            count += 1
    return count


def _load_collaboration(db: Session, path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source = db.query(Employee).filter(Employee.external_id == row["source_external_id"]).first()
            target = db.query(Employee).filter(Employee.external_id == row["target_external_id"]).first()
            if not source or not target:
                continue
            existing = (
                db.query(CollaborationEdge)
                .filter(
                    CollaborationEdge.source_employee_id == source.id,
                    CollaborationEdge.target_employee_id == target.id,
                )
                .first()
            )
            if existing:
                existing.interaction_count = int(row["interaction_count"])
            else:
                db.add(
                    CollaborationEdge(
                        source_employee_id=source.id,
                        target_employee_id=target.id,
                        interaction_count=int(row["interaction_count"]),
                    )
                )
            count += 1
    return count
