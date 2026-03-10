from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.entities import (
    Employee,
    EmployeeRiskSnapshot,
    EngagementMetric,
    PerformanceMetric,
    WorkloadMetric,
)
from app.schemas.hr import OrgHealthResponse, ProfileResponse, RiskRecord
from app.services.risk_scoring import score_attrition, score_burnout


def _latest_metric_value(db: Session, model, employee_id: int):
    return (
        db.query(model)
        .filter(model.employee_id == employee_id)
        .order_by(model.snapshot_date.desc())
        .first()
    )


def build_employee_profile(db: Session, employee_id: int) -> ProfileResponse | None:
    row = (
        db.query(Employee, EmployeeRiskSnapshot)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .filter(Employee.id == employee_id)
        .first()
    )
    if not row:
        return None

    employee, snapshot = row
    if snapshot:
        return ProfileResponse(
            employee=employee,
            engagement_score=snapshot.engagement_score,
            sentiment_score=snapshot.sentiment_score,
            overtime_hours=snapshot.overtime_hours,
            meeting_hours=snapshot.meeting_hours,
            performance_rating=snapshot.performance_rating,
            goal_completion_pct=snapshot.goal_completion_pct,
            attrition_risk=snapshot.attrition_risk,
            burnout_risk=snapshot.burnout_risk,
        )

    # Fallback for employees whose snapshots are not yet refreshed.
    engagement = _latest_metric_value(db, EngagementMetric, employee_id)
    workload = _latest_metric_value(db, WorkloadMetric, employee_id)
    performance = _latest_metric_value(db, PerformanceMetric, employee_id)

    attrition_risk = score_attrition(
        engagement.engagement_score if engagement else None,
        engagement.sentiment_score if engagement else None,
        workload.overtime_hours if workload else None,
        performance.performance_rating if performance else None,
    )
    burnout_risk = score_burnout(
        engagement.engagement_score if engagement else None,
        workload.overtime_hours if workload else None,
        workload.meeting_hours if workload else None,
        workload.after_hours_messages if workload else None,
    )

    return ProfileResponse(
        employee=employee,
        engagement_score=engagement.engagement_score if engagement else None,
        sentiment_score=engagement.sentiment_score if engagement else None,
        overtime_hours=workload.overtime_hours if workload else None,
        meeting_hours=workload.meeting_hours if workload else None,
        performance_rating=performance.performance_rating if performance else None,
        goal_completion_pct=performance.goal_completion_pct if performance else None,
        attrition_risk=attrition_risk,
        burnout_risk=burnout_risk,
    )


def get_org_health(db: Session, attrition_threshold: float, burnout_threshold: float) -> OrgHealthResponse:
    active_headcount = (
        db.query(func.count(Employee.id))
        .filter(Employee.employment_status == "active")
        .scalar()
        or 0
    )
    if active_headcount == 0:
        return OrgHealthResponse(
            active_headcount=0,
            average_engagement=0,
            average_sentiment=0,
            high_attrition_risk_count=0,
            high_burnout_risk_count=0,
        )

    aggregate_row = (
        db.query(
            func.avg(EmployeeRiskSnapshot.engagement_score),
            func.avg(EmployeeRiskSnapshot.sentiment_score),
            func.sum(
                case(
                    (EmployeeRiskSnapshot.attrition_risk >= attrition_threshold, 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (EmployeeRiskSnapshot.burnout_risk >= burnout_threshold, 1),
                    else_=0,
                )
            ),
        )
        .join(Employee, Employee.id == EmployeeRiskSnapshot.employee_id)
        .filter(Employee.employment_status == "active")
        .one()
    )

    return OrgHealthResponse(
        active_headcount=active_headcount,
        average_engagement=round(float(aggregate_row[0] or 0), 3),
        average_sentiment=round(float(aggregate_row[1] or 0), 3),
        high_attrition_risk_count=int(aggregate_row[2] or 0),
        high_burnout_risk_count=int(aggregate_row[3] or 0),
    )


def list_risk_records(db: Session, limit: int = 20, offset: int = 0) -> list[RiskRecord]:
    rows = (
        db.query(
            EmployeeRiskSnapshot.employee_id,
            Employee.full_name,
            Employee.department,
            EmployeeRiskSnapshot.attrition_risk,
            EmployeeRiskSnapshot.burnout_risk,
        )
        .join(Employee, Employee.id == EmployeeRiskSnapshot.employee_id)
        .filter(Employee.employment_status == "active")
        .order_by(
            EmployeeRiskSnapshot.attrition_risk.desc(),
            EmployeeRiskSnapshot.burnout_risk.desc(),
            EmployeeRiskSnapshot.employee_id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        RiskRecord(
            employee_id=row.employee_id,
            employee_name=row.full_name,
            department=row.department,
            attrition_risk=row.attrition_risk,
            burnout_risk=row.burnout_risk,
        )
        for row in rows
    ]


def headcount_by_department(db: Session) -> dict[str, int]:
    rows = (
        db.query(Employee.department, func.count(Employee.id))
        .filter(Employee.employment_status == "active")
        .group_by(Employee.department)
        .all()
    )
    return {department: count for department, count in rows}
