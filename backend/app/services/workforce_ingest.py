from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.entities import (
    CollaborationEdge,
    Employee,
    EngagementMetric,
    IngestionRun,
    PerformanceMetric,
    WorkloadMetric,
)
from app.schemas.hr import WorkforceIngestRequest, WorkforceIngestResponse
from app.services.risk_snapshot import refresh_risk_snapshots


def _collect_external_ids(payload: WorkforceIngestRequest) -> set[str]:
    ids: set[str] = set()
    ids.update(record.external_id for record in payload.employees)
    ids.update(record.external_id for record in payload.engagement_metrics)
    ids.update(record.external_id for record in payload.workload_metrics)
    ids.update(record.external_id for record in payload.performance_metrics)
    ids.update(record.source_external_id for record in payload.collaboration_edges)
    ids.update(record.target_external_id for record in payload.collaboration_edges)
    return {external_id for external_id in ids if external_id}


def _employee_map(db: Session, external_ids: Iterable[str]) -> dict[str, Employee]:
    unique_ids = sorted(set(external_ids))
    if not unique_ids:
        return {}
    rows = db.query(Employee).filter(Employee.external_id.in_(unique_ids)).all()
    return {employee.external_id: employee for employee in rows}


def ingest_workforce_payload(
    db: Session,
    payload: WorkforceIngestRequest,
    *,
    snapshot_batch_size: int,
) -> WorkforceIngestResponse:
    external_ids = _collect_external_ids(payload)
    employees_by_external_id = _employee_map(db, external_ids)

    employee_upserts = 0
    metric_upserts = 0
    edge_upserts = 0
    touched_employee_ids: set[int] = set()
    manager_links: dict[str, str] = {}

    for row in payload.employees:
        employee = employees_by_external_id.get(row.external_id)
        if employee:
            employee.full_name = row.full_name
            employee.email = row.email
            employee.department = row.department
            employee.role = row.role
            employee.location = row.location
            employee.hire_date = row.hire_date
            employee.employment_status = row.employment_status
            employee.base_salary = Decimal(str(row.base_salary))
        else:
            employee = Employee(
                external_id=row.external_id,
                full_name=row.full_name,
                email=row.email,
                department=row.department,
                role=row.role,
                location=row.location,
                hire_date=row.hire_date,
                employment_status=row.employment_status,
                base_salary=Decimal(str(row.base_salary)),
            )
            db.add(employee)
            employees_by_external_id[row.external_id] = employee

        employee_upserts += 1
        if row.manager_external_id:
            manager_links[row.external_id] = row.manager_external_id

    db.flush()

    for employee_external_id, manager_external_id in manager_links.items():
        employee = employees_by_external_id.get(employee_external_id)
        manager = employees_by_external_id.get(manager_external_id)
        if not employee:
            continue
        if manager_external_id and not manager:
            raise ValueError(f"Unknown manager_external_id: {manager_external_id}")
        employee.manager_id = manager.id if manager else None

    for row in payload.engagement_metrics:
        employee = employees_by_external_id.get(row.external_id)
        if not employee:
            raise ValueError(f"Unknown employee external_id in engagement_metrics: {row.external_id}")

        existing = (
            db.query(EngagementMetric)
            .filter(
                EngagementMetric.employee_id == employee.id,
                EngagementMetric.snapshot_date == row.snapshot_date,
            )
            .first()
        )
        if existing:
            existing.engagement_score = row.engagement_score
            existing.sentiment_score = row.sentiment_score
        else:
            db.add(
                EngagementMetric(
                    employee_id=employee.id,
                    snapshot_date=row.snapshot_date,
                    engagement_score=row.engagement_score,
                    sentiment_score=row.sentiment_score,
                )
            )

        metric_upserts += 1
        touched_employee_ids.add(employee.id)

    for row in payload.workload_metrics:
        employee = employees_by_external_id.get(row.external_id)
        if not employee:
            raise ValueError(f"Unknown employee external_id in workload_metrics: {row.external_id}")

        existing = (
            db.query(WorkloadMetric)
            .filter(
                WorkloadMetric.employee_id == employee.id,
                WorkloadMetric.snapshot_date == row.snapshot_date,
            )
            .first()
        )
        if existing:
            existing.overtime_hours = row.overtime_hours
            existing.meeting_hours = row.meeting_hours
            existing.after_hours_messages = row.after_hours_messages
        else:
            db.add(
                WorkloadMetric(
                    employee_id=employee.id,
                    snapshot_date=row.snapshot_date,
                    overtime_hours=row.overtime_hours,
                    meeting_hours=row.meeting_hours,
                    after_hours_messages=row.after_hours_messages,
                )
            )

        metric_upserts += 1
        touched_employee_ids.add(employee.id)

    for row in payload.performance_metrics:
        employee = employees_by_external_id.get(row.external_id)
        if not employee:
            raise ValueError(f"Unknown employee external_id in performance_metrics: {row.external_id}")

        existing = (
            db.query(PerformanceMetric)
            .filter(
                PerformanceMetric.employee_id == employee.id,
                PerformanceMetric.snapshot_date == row.snapshot_date,
            )
            .first()
        )
        if existing:
            existing.performance_rating = row.performance_rating
            existing.goal_completion_pct = row.goal_completion_pct
        else:
            db.add(
                PerformanceMetric(
                    employee_id=employee.id,
                    snapshot_date=row.snapshot_date,
                    performance_rating=row.performance_rating,
                    goal_completion_pct=row.goal_completion_pct,
                )
            )

        metric_upserts += 1
        touched_employee_ids.add(employee.id)

    for row in payload.collaboration_edges:
        source = employees_by_external_id.get(row.source_external_id)
        target = employees_by_external_id.get(row.target_external_id)
        if not source or not target:
            raise ValueError(
                f"Unknown edge external_id(s): source={row.source_external_id}, target={row.target_external_id}"
            )

        existing = (
            db.query(CollaborationEdge)
            .filter(
                CollaborationEdge.source_employee_id == source.id,
                CollaborationEdge.target_employee_id == target.id,
            )
            .first()
        )
        if existing:
            existing.interaction_count = row.interaction_count
            existing.last_interaction_at = datetime.utcnow()
        else:
            db.add(
                CollaborationEdge(
                    source_employee_id=source.id,
                    target_employee_id=target.id,
                    interaction_count=row.interaction_count,
                )
            )

        edge_upserts += 1

    touched_employee_ids.update(
        employee.id for employee in employees_by_external_id.values() if employee.id is not None
    )
    snapshots_refreshed = refresh_risk_snapshots(
        db,
        batch_size=max(1, snapshot_batch_size),
        only_employee_ids=sorted(touched_employee_ids),
    )

    records_received = (
        len(payload.employees)
        + len(payload.engagement_metrics)
        + len(payload.workload_metrics)
        + len(payload.performance_metrics)
        + len(payload.collaboration_edges)
    )

    run = IngestionRun(
        source=payload.source,
        records_received=records_received,
        employees_upserted=employee_upserts,
        metrics_upserted=metric_upserts,
        edges_upserted=edge_upserts,
        status="success",
        details=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return WorkforceIngestResponse(
        run_id=run.id,
        source=payload.source,
        records_received=records_received,
        employees_upserted=employee_upserts,
        metrics_upserted=metric_upserts,
        edges_upserted=edge_upserts,
        snapshots_refreshed=snapshots_refreshed,
    )
