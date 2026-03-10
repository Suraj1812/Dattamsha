from __future__ import annotations

from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session

from app.models.entities import Employee, EmployeeRiskSnapshot, Nudge
from app.schemas.hr import ManagerTeamMember, ManagerTeamOverviewResponse


def get_manager_team_overview(
    db: Session,
    *,
    manager_id: int,
    member_search: str | None = None,
    risk_band: str | None = None,
) -> ManagerTeamOverviewResponse | None:
    manager = db.query(Employee).filter(Employee.id == manager_id).first()
    if not manager:
        return None

    open_nudge_subquery = (
        db.query(Nudge.employee_id.label("employee_id"), func.count(Nudge.id).label("open_nudges"))
        .filter(Nudge.status == "open")
        .group_by(Nudge.employee_id)
        .subquery()
    )

    query = (
        db.query(Employee, EmployeeRiskSnapshot, open_nudge_subquery.c.open_nudges)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .outerjoin(open_nudge_subquery, open_nudge_subquery.c.employee_id == Employee.id)
        .filter(Employee.manager_id == manager_id, Employee.employment_status == "active")
    )

    if member_search:
        pattern = f"%{member_search.strip()}%"
        query = query.filter(
            (Employee.full_name.ilike(pattern))
            | (Employee.department.ilike(pattern))
            | (Employee.role.ilike(pattern))
            | (Employee.external_id.ilike(pattern))
            | (cast(Employee.id, String).ilike(pattern))
        )

    rows = query.all()

    if not rows:
        return ManagerTeamOverviewResponse(
            manager_id=manager.id,
            manager_name=manager.full_name,
            team_size=0,
            average_engagement=0,
            average_attrition_risk=0,
            average_burnout_risk=0,
            open_nudges=0,
            recommended_actions=["No active direct reports found for this manager."],
            members=[],
        )

    members: list[ManagerTeamMember] = []
    total_engagement = 0.0
    total_attrition = 0.0
    total_burnout = 0.0
    open_nudges = 0

    def risk_band_matches(attrition: float, burnout: float) -> bool:
        if not risk_band or risk_band == "all":
            return True
        value = max(attrition, burnout)
        if risk_band == "high":
            return value >= 0.7
        if risk_band == "medium":
            return 0.5 <= value < 0.7
        if risk_band == "low":
            return value < 0.5
        return True

    for employee, snapshot, member_open_nudges in rows:
        engagement = float(snapshot.engagement_score) if snapshot and snapshot.engagement_score is not None else 0.0
        attrition = float(snapshot.attrition_risk) if snapshot else 0.0
        burnout = float(snapshot.burnout_risk) if snapshot else 0.0
        member_nudges = int(member_open_nudges or 0)

        if not risk_band_matches(attrition, burnout):
            continue

        members.append(
            ManagerTeamMember(
                employee_id=employee.id,
                full_name=employee.full_name,
                department=employee.department,
                role=employee.role,
                engagement_score=engagement,
                attrition_risk=attrition,
                burnout_risk=burnout,
                open_nudges=member_nudges,
            )
        )

        total_engagement += engagement
        total_attrition += attrition
        total_burnout += burnout
        open_nudges += member_nudges

    team_size = len(members)
    avg_engagement = total_engagement / team_size if team_size else 0.0
    avg_attrition = total_attrition / team_size if team_size else 0.0
    avg_burnout = total_burnout / team_size if team_size else 0.0

    recommended_actions: list[str] = []
    if avg_attrition >= 0.65:
        recommended_actions.append("Run retention 1:1s this week for top attrition-risk employees.")
    if avg_burnout >= 0.7:
        recommended_actions.append("Rebalance workload and reduce after-hours load for high burnout-risk members.")
    if avg_engagement <= 0.45:
        recommended_actions.append("Schedule team engagement pulse and manager coaching review.")
    if open_nudges >= max(2, team_size // 2):
        recommended_actions.append("Clear open nudges in priority order and capture intervention feedback.")
    if not recommended_actions:
        recommended_actions.append("Team risk profile is stable. Continue weekly check-ins and metric monitoring.")

    members.sort(key=lambda row: (row.attrition_risk + row.burnout_risk, row.open_nudges), reverse=True)

    return ManagerTeamOverviewResponse(
        manager_id=manager.id,
        manager_name=manager.full_name,
        team_size=team_size,
        average_engagement=round(avg_engagement, 3),
        average_attrition_risk=round(avg_attrition, 3),
        average_burnout_risk=round(avg_burnout, 3),
        open_nudges=open_nudges,
        recommended_actions=recommended_actions,
        members=members,
    )
