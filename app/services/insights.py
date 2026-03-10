from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Employee, EngagementMetric, PerformanceMetric, WorkloadMetric
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
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

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
    employees = db.query(Employee).filter(Employee.employment_status == "active").all()
    if not employees:
        return OrgHealthResponse(
            active_headcount=0,
            average_engagement=0,
            average_sentiment=0,
            high_attrition_risk_count=0,
            high_burnout_risk_count=0,
        )

    engagement_values: list[float] = []
    sentiment_values: list[float] = []
    high_attrition = 0
    high_burnout = 0

    for employee in employees:
        profile = build_employee_profile(db, employee.id)
        if not profile:
            continue

        if profile.engagement_score is not None:
            engagement_values.append(profile.engagement_score)
        if profile.sentiment_score is not None:
            sentiment_values.append(profile.sentiment_score)

        if profile.attrition_risk and profile.attrition_risk >= attrition_threshold:
            high_attrition += 1
        if profile.burnout_risk and profile.burnout_risk >= burnout_threshold:
            high_burnout += 1

    return OrgHealthResponse(
        active_headcount=len(employees),
        average_engagement=round(sum(engagement_values) / len(engagement_values), 3)
        if engagement_values
        else 0,
        average_sentiment=round(sum(sentiment_values) / len(sentiment_values), 3)
        if sentiment_values
        else 0,
        high_attrition_risk_count=high_attrition,
        high_burnout_risk_count=high_burnout,
    )


def list_risk_records(db: Session, limit: int = 20) -> list[RiskRecord]:
    employees = db.query(Employee).filter(Employee.employment_status == "active").all()
    rows: list[RiskRecord] = []

    for employee in employees:
        profile = build_employee_profile(db, employee.id)
        if not profile or profile.attrition_risk is None or profile.burnout_risk is None:
            continue
        rows.append(
            RiskRecord(
                employee_id=employee.id,
                employee_name=employee.full_name,
                department=employee.department,
                attrition_risk=profile.attrition_risk,
                burnout_risk=profile.burnout_risk,
            )
        )

    rows.sort(key=lambda r: (r.attrition_risk, r.burnout_risk), reverse=True)
    return rows[:limit]


def headcount_by_department(db: Session) -> dict[str, int]:
    rows = (
        db.query(Employee.department, func.count(Employee.id))
        .filter(Employee.employment_status == "active")
        .group_by(Employee.department)
        .all()
    )
    return {department: count for department, count in rows}
