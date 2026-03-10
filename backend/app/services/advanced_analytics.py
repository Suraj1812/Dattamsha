from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import pstdev
from typing import Literal

from sqlalchemy.orm import Session, aliased

from app.models.entities import Employee, EmployeeRiskSnapshot, EngagementMetric, PerformanceMetric, WorkloadMetric
from app.schemas.hr import (
    CohortAnalyticsResponse,
    CohortMetric,
    EmployeeTimelinePoint,
    EmployeeTimelineResponse,
    RiskAnomaly,
    RiskAnomalyResponse,
    RiskTrendPoint,
)
from app.services.risk_scoring import score_attrition, score_burnout


CohortDimension = Literal["department", "location", "manager"]


def get_risk_trends(
    db: Session,
    *,
    days: int = 90,
    search_date: str | None = None,
) -> list[RiskTrendPoint]:
    window_days = max(1, min(days, 365))
    start_date = date.today() - timedelta(days=window_days - 1)

    timeline: dict[tuple[int, date], dict[str, float | int | None]] = defaultdict(dict)

    engagement_rows = (
        db.query(EngagementMetric)
        .filter(EngagementMetric.snapshot_date >= start_date)
        .all()
    )
    for row in engagement_rows:
        key = (row.employee_id, row.snapshot_date)
        timeline[key]["engagement_score"] = row.engagement_score
        timeline[key]["sentiment_score"] = row.sentiment_score

    workload_rows = (
        db.query(WorkloadMetric)
        .filter(WorkloadMetric.snapshot_date >= start_date)
        .all()
    )
    for row in workload_rows:
        key = (row.employee_id, row.snapshot_date)
        timeline[key]["overtime_hours"] = row.overtime_hours
        timeline[key]["meeting_hours"] = row.meeting_hours
        timeline[key]["after_hours_messages"] = row.after_hours_messages

    performance_rows = (
        db.query(PerformanceMetric)
        .filter(PerformanceMetric.snapshot_date >= start_date)
        .all()
    )
    for row in performance_rows:
        key = (row.employee_id, row.snapshot_date)
        timeline[key]["performance_rating"] = row.performance_rating
        timeline[key]["goal_completion_pct"] = row.goal_completion_pct

    by_date: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for (_, snapshot_date), values in timeline.items():
        engagement_score = values.get("engagement_score")
        sentiment_score = values.get("sentiment_score")
        overtime_hours = values.get("overtime_hours")
        meeting_hours = values.get("meeting_hours")
        after_hours_messages = values.get("after_hours_messages")
        performance_rating = values.get("performance_rating")

        attrition_risk = score_attrition(
            float(engagement_score) if engagement_score is not None else None,
            float(sentiment_score) if sentiment_score is not None else None,
            float(overtime_hours) if overtime_hours is not None else None,
            float(performance_rating) if performance_rating is not None else None,
        )
        burnout_risk = score_burnout(
            float(engagement_score) if engagement_score is not None else None,
            float(overtime_hours) if overtime_hours is not None else None,
            float(meeting_hours) if meeting_hours is not None else None,
            int(after_hours_messages) if after_hours_messages is not None else None,
        )

        by_date[snapshot_date]["attrition_sum"] += attrition_risk
        by_date[snapshot_date]["burnout_sum"] += burnout_risk
        by_date[snapshot_date]["risk_count"] += 1

        if engagement_score is not None:
            by_date[snapshot_date]["engagement_sum"] += float(engagement_score)
            by_date[snapshot_date]["engagement_count"] += 1

    active_hire_dates = [
        hire_date
        for (hire_date,) in (
            db.query(Employee.hire_date)
            .filter(Employee.employment_status == "active")
            .all()
        )
        if hire_date is not None
    ]

    points: list[RiskTrendPoint] = []
    for snapshot_date in sorted(by_date.keys()):
        entry = by_date[snapshot_date]
        risk_count = int(entry.get("risk_count", 0))
        engagement_count = int(entry.get("engagement_count", 0))
        headcount = sum(1 for hire_date in active_hire_dates if hire_date <= snapshot_date)

        points.append(
            RiskTrendPoint(
                snapshot_date=snapshot_date,
                active_headcount=headcount,
                average_engagement=round(
                    float(entry.get("engagement_sum", 0.0) / engagement_count) if engagement_count else 0.0,
                    3,
                ),
                average_attrition_risk=round(
                    float(entry.get("attrition_sum", 0.0) / risk_count) if risk_count else 0.0,
                    3,
                ),
                average_burnout_risk=round(
                    float(entry.get("burnout_sum", 0.0) / risk_count) if risk_count else 0.0,
                    3,
                ),
            )
        )

    if search_date:
        needle = search_date.strip()
        points = [point for point in points if needle in point.snapshot_date.isoformat()]

    return points


def get_cohort_analytics(
    db: Session,
    *,
    dimension: CohortDimension,
    attrition_threshold: float,
    burnout_threshold: float,
    search: str | None = None,
) -> CohortAnalyticsResponse:
    manager_alias = aliased(Employee)
    rows = (
        db.query(Employee, EmployeeRiskSnapshot, manager_alias.full_name)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .outerjoin(manager_alias, manager_alias.id == Employee.manager_id)
        .filter(Employee.employment_status == "active")
        .all()
    )

    grouped: dict[str, dict[str, float | int]] = defaultdict(lambda: defaultdict(float))

    for employee, snapshot, manager_name in rows:
        if dimension == "department":
            group_key = employee.department or "Unknown"
        elif dimension == "location":
            group_key = employee.location or "Unknown"
        else:
            group_key = manager_name or "Unassigned"

        grouped[group_key]["headcount"] += 1

        engagement_value = snapshot.engagement_score if snapshot and snapshot.engagement_score is not None else 0.0
        attrition_value = snapshot.attrition_risk if snapshot else 0.0
        burnout_value = snapshot.burnout_risk if snapshot else 0.0

        grouped[group_key]["engagement_sum"] += engagement_value
        grouped[group_key]["attrition_sum"] += attrition_value
        grouped[group_key]["burnout_sum"] += burnout_value

        if attrition_value >= attrition_threshold:
            grouped[group_key]["high_attrition_count"] += 1
        if burnout_value >= burnout_threshold:
            grouped[group_key]["high_burnout_count"] += 1

    cohorts = []
    for group_key, values in grouped.items():
        headcount = int(values.get("headcount", 0))
        if headcount == 0:
            continue
        cohorts.append(
            CohortMetric(
                cohort=group_key,
                headcount=headcount,
                avg_engagement=round(float(values.get("engagement_sum", 0.0) / headcount), 3),
                avg_attrition_risk=round(float(values.get("attrition_sum", 0.0) / headcount), 3),
                avg_burnout_risk=round(float(values.get("burnout_sum", 0.0) / headcount), 3),
                high_attrition_count=int(values.get("high_attrition_count", 0)),
                high_burnout_count=int(values.get("high_burnout_count", 0)),
            )
        )

    if search:
        needle = search.strip().lower()
        cohorts = [row for row in cohorts if needle in row.cohort.lower()]

    cohorts.sort(key=lambda row: (row.headcount, row.avg_attrition_risk + row.avg_burnout_risk), reverse=True)
    return CohortAnalyticsResponse(dimension=dimension, cohorts=cohorts)


def detect_risk_anomalies(
    db: Session,
    *,
    dimension: CohortDimension,
    attrition_threshold: float,
    burnout_threshold: float,
    min_population: int = 3,
    search: str | None = None,
    severity: str | None = None,
) -> RiskAnomalyResponse:
    cohort_summary = get_cohort_analytics(
        db,
        dimension=dimension,
        attrition_threshold=attrition_threshold,
        burnout_threshold=burnout_threshold,
        search=search,
    )

    risk_values = (
        db.query(EmployeeRiskSnapshot.attrition_risk, EmployeeRiskSnapshot.burnout_risk)
        .join(Employee, Employee.id == EmployeeRiskSnapshot.employee_id)
        .filter(Employee.employment_status == "active")
        .all()
    )
    attrition_values = [float(attrition or 0) for attrition, _ in risk_values]
    burnout_values = [float(burnout or 0) for _, burnout in risk_values]

    if not attrition_values or not burnout_values:
        return RiskAnomalyResponse(dimension=dimension, anomalies=[])

    attrition_baseline = sum(attrition_values) / len(attrition_values)
    burnout_baseline = sum(burnout_values) / len(burnout_values)
    attrition_std = pstdev(attrition_values) if len(attrition_values) > 1 else 0.0
    burnout_std = pstdev(burnout_values) if len(burnout_values) > 1 else 0.0

    def severity_from_delta(delta: float) -> str:
        if delta >= 0.18:
            return "high"
        if delta >= 0.1:
            return "medium"
        return "low"

    anomalies: list[RiskAnomaly] = []
    for cohort in cohort_summary.cohorts:
        if cohort.headcount < min_population:
            continue

        attrition_delta = cohort.avg_attrition_risk - attrition_baseline
        burnout_delta = cohort.avg_burnout_risk - burnout_baseline

        attrition_cutoff = max(0.08, attrition_std * 0.75)
        burnout_cutoff = max(0.08, burnout_std * 0.75)

        if attrition_delta >= attrition_cutoff:
            anomalies.append(
                RiskAnomaly(
                    cohort=cohort.cohort,
                    metric="attrition_risk",
                    value=round(cohort.avg_attrition_risk, 3),
                    baseline=round(attrition_baseline, 3),
                    delta=round(attrition_delta, 3),
                    severity=severity_from_delta(attrition_delta),
                )
            )

        if burnout_delta >= burnout_cutoff:
            anomalies.append(
                RiskAnomaly(
                    cohort=cohort.cohort,
                    metric="burnout_risk",
                    value=round(cohort.avg_burnout_risk, 3),
                    baseline=round(burnout_baseline, 3),
                    delta=round(burnout_delta, 3),
                    severity=severity_from_delta(burnout_delta),
                )
            )

    if severity and severity != "all":
        anomalies = [row for row in anomalies if row.severity == severity]

    anomalies.sort(key=lambda row: row.delta, reverse=True)
    return RiskAnomalyResponse(dimension=dimension, anomalies=anomalies)


def build_employee_timeline(
    db: Session,
    *,
    employee_id: int,
    days: int = 180,
    limit: int = 60,
    search_date: str | None = None,
    risk_band: str | None = None,
) -> EmployeeTimelineResponse:
    window_days = max(1, min(days, 730))
    point_limit = max(1, min(limit, 365))
    start_date = date.today() - timedelta(days=window_days - 1)

    timeline: dict[date, EmployeeTimelinePoint] = {}

    engagement_rows = (
        db.query(EngagementMetric)
        .filter(
            EngagementMetric.employee_id == employee_id,
            EngagementMetric.snapshot_date >= start_date,
        )
        .all()
    )
    for row in engagement_rows:
        point = timeline.setdefault(row.snapshot_date, EmployeeTimelinePoint(snapshot_date=row.snapshot_date))
        point.engagement_score = row.engagement_score
        point.sentiment_score = row.sentiment_score

    workload_rows = (
        db.query(WorkloadMetric)
        .filter(
            WorkloadMetric.employee_id == employee_id,
            WorkloadMetric.snapshot_date >= start_date,
        )
        .all()
    )
    for row in workload_rows:
        point = timeline.setdefault(row.snapshot_date, EmployeeTimelinePoint(snapshot_date=row.snapshot_date))
        point.overtime_hours = row.overtime_hours
        point.meeting_hours = row.meeting_hours
        point.after_hours_messages = row.after_hours_messages

    performance_rows = (
        db.query(PerformanceMetric)
        .filter(
            PerformanceMetric.employee_id == employee_id,
            PerformanceMetric.snapshot_date >= start_date,
        )
        .all()
    )
    for row in performance_rows:
        point = timeline.setdefault(row.snapshot_date, EmployeeTimelinePoint(snapshot_date=row.snapshot_date))
        point.performance_rating = row.performance_rating
        point.goal_completion_pct = row.goal_completion_pct

    points = sorted(timeline.values(), key=lambda row: row.snapshot_date, reverse=True)[:point_limit]
    for point in points:
        point.attrition_risk = score_attrition(
            point.engagement_score,
            point.sentiment_score,
            point.overtime_hours,
            point.performance_rating,
        )
        point.burnout_risk = score_burnout(
            point.engagement_score,
            point.overtime_hours,
            point.meeting_hours,
            point.after_hours_messages,
        )

    if search_date:
        needle = search_date.strip().lower()
        points = [point for point in points if needle in point.snapshot_date.isoformat().lower()]

    if risk_band and risk_band != "all":
        filtered_points: list[EmployeeTimelinePoint] = []
        for point in points:
            risk_value = max(point.attrition_risk or 0.0, point.burnout_risk or 0.0)
            if risk_band == "high" and risk_value >= 0.7:
                filtered_points.append(point)
            elif risk_band == "medium" and 0.5 <= risk_value < 0.7:
                filtered_points.append(point)
            elif risk_band == "low" and risk_value < 0.5:
                filtered_points.append(point)
        points = filtered_points

    return EmployeeTimelineResponse(employee_id=employee_id, points=points)
