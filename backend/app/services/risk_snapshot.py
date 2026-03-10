from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    Employee,
    EmployeeRiskSnapshot,
    EngagementMetric,
    PerformanceMetric,
    WorkloadMetric,
)
from app.services.risk_scoring import score_attrition, score_burnout


def _chunked(values: list[int], size: int) -> list[list[int]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _latest_metric_subquery(db: Session, model, value_columns: list[str], employee_ids: list[int]):
    ranked = (
        db.query(
            model.employee_id.label("employee_id"),
            *(getattr(model, col).label(col) for col in value_columns),
            model.snapshot_date.label("snapshot_date"),
            func.row_number()
            .over(partition_by=model.employee_id, order_by=model.snapshot_date.desc())
            .label("rn"),
        )
        .filter(model.employee_id.in_(employee_ids))
        .subquery()
    )

    return (
        db.query(
            ranked.c.employee_id.label("employee_id"),
            *(getattr(ranked.c, col).label(col) for col in value_columns),
            ranked.c.snapshot_date.label("snapshot_date"),
        )
        .filter(ranked.c.rn == 1)
        .subquery()
    )


def _refresh_snapshot_batch(db: Session, employee_ids: list[int]) -> int:
    if not employee_ids:
        return 0

    engagement = _latest_metric_subquery(
        db,
        EngagementMetric,
        ["engagement_score", "sentiment_score"],
        employee_ids,
    )
    workload = _latest_metric_subquery(
        db,
        WorkloadMetric,
        ["overtime_hours", "meeting_hours", "after_hours_messages"],
        employee_ids,
    )
    performance = _latest_metric_subquery(
        db,
        PerformanceMetric,
        ["performance_rating", "goal_completion_pct"],
        employee_ids,
    )

    rows = (
        db.query(
            Employee.id.label("employee_id"),
            engagement.c.engagement_score,
            engagement.c.sentiment_score,
            engagement.c.snapshot_date.label("engagement_snapshot"),
            workload.c.overtime_hours,
            workload.c.meeting_hours,
            workload.c.after_hours_messages,
            workload.c.snapshot_date.label("workload_snapshot"),
            performance.c.performance_rating,
            performance.c.goal_completion_pct,
            performance.c.snapshot_date.label("performance_snapshot"),
        )
        .filter(Employee.id.in_(employee_ids), Employee.employment_status == "active")
        .outerjoin(engagement, engagement.c.employee_id == Employee.id)
        .outerjoin(workload, workload.c.employee_id == Employee.id)
        .outerjoin(performance, performance.c.employee_id == Employee.id)
        .all()
    )

    existing = (
        db.query(EmployeeRiskSnapshot)
        .filter(EmployeeRiskSnapshot.employee_id.in_(employee_ids))
        .all()
    )
    existing_by_employee_id = {row.employee_id: row for row in existing}

    refreshed_at = datetime.utcnow()
    upserted = 0

    for row in rows:
        attrition_risk = score_attrition(
            row.engagement_score,
            row.sentiment_score,
            row.overtime_hours,
            row.performance_rating,
        )
        burnout_risk = score_burnout(
            row.engagement_score,
            row.overtime_hours,
            row.meeting_hours,
            row.after_hours_messages,
        )

        candidate_dates = [
            snapshot_date
            for snapshot_date in [
                row.engagement_snapshot,
                row.workload_snapshot,
                row.performance_snapshot,
            ]
            if snapshot_date is not None
        ]
        snapshot_date = max(candidate_dates) if candidate_dates else date.today()

        target = existing_by_employee_id.get(row.employee_id)
        if target:
            target.snapshot_date = snapshot_date
            target.engagement_score = row.engagement_score
            target.sentiment_score = row.sentiment_score
            target.overtime_hours = row.overtime_hours
            target.meeting_hours = row.meeting_hours
            target.after_hours_messages = row.after_hours_messages
            target.performance_rating = row.performance_rating
            target.goal_completion_pct = row.goal_completion_pct
            target.attrition_risk = attrition_risk
            target.burnout_risk = burnout_risk
            target.refreshed_at = refreshed_at
        else:
            db.add(
                EmployeeRiskSnapshot(
                    employee_id=row.employee_id,
                    snapshot_date=snapshot_date,
                    engagement_score=row.engagement_score,
                    sentiment_score=row.sentiment_score,
                    overtime_hours=row.overtime_hours,
                    meeting_hours=row.meeting_hours,
                    after_hours_messages=row.after_hours_messages,
                    performance_rating=row.performance_rating,
                    goal_completion_pct=row.goal_completion_pct,
                    attrition_risk=attrition_risk,
                    burnout_risk=burnout_risk,
                    refreshed_at=refreshed_at,
                )
            )

        upserted += 1

    return upserted


def refresh_risk_snapshots(
    db: Session,
    *,
    batch_size: int = 5000,
    only_employee_ids: list[int] | None = None,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    processed = 0

    if only_employee_ids is not None:
        for chunk in _chunked(sorted(set(only_employee_ids)), batch_size):
            processed += _refresh_snapshot_batch(db, chunk)
            db.commit()
        return processed

    last_id = 0
    while True:
        employee_ids = [
            employee_id
            for (employee_id,) in (
                db.query(Employee.id)
                .filter(Employee.employment_status == "active", Employee.id > last_id)
                .order_by(Employee.id.asc())
                .limit(batch_size)
                .all()
            )
        ]

        if not employee_ids:
            break

        processed += _refresh_snapshot_batch(db, employee_ids)
        db.commit()
        last_id = employee_ids[-1]

    return processed
