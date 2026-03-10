from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Employee, EmployeeRiskSnapshot, Nudge


def _severity(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.7:
        return "medium"
    return "low"


def _create_or_update_nudge(
    db: Session,
    employee_id: int,
    nudge_type: str,
    severity: str,
    message: str,
    evidence: str,
) -> Nudge:
    existing = (
        db.query(Nudge)
        .filter(
            Nudge.employee_id == employee_id,
            Nudge.nudge_type == nudge_type,
            Nudge.status == "open",
        )
        .first()
    )

    if existing:
        existing.severity = severity
        existing.message = message
        existing.evidence = evidence
        return existing

    nudge = Nudge(
        employee_id=employee_id,
        nudge_type=nudge_type,
        severity=severity,
        message=message,
        evidence=evidence,
        status="open",
        created_at=datetime.utcnow(),
    )
    db.add(nudge)
    return nudge


def generate_nudges(db: Session) -> list[Nudge]:
    settings = get_settings()
    candidate_rows = (
        db.query(Employee, EmployeeRiskSnapshot)
        .join(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .filter(
            Employee.employment_status == "active",
            or_(
                EmployeeRiskSnapshot.attrition_risk >= settings.nudge_threshold_attrition,
                EmployeeRiskSnapshot.burnout_risk >= settings.nudge_threshold_burnout,
            ),
        )
        .order_by(
            EmployeeRiskSnapshot.attrition_risk.desc(),
            EmployeeRiskSnapshot.burnout_risk.desc(),
            EmployeeRiskSnapshot.employee_id.asc(),
        )
        .limit(settings.nudge_generation_batch_size)
        .all()
    )

    created_or_updated: list[Nudge] = []
    for employee, snapshot in candidate_rows:
        if snapshot.attrition_risk >= settings.nudge_threshold_attrition:
            nudge = _create_or_update_nudge(
                db=db,
                employee_id=employee.id,
                nudge_type="attrition_risk",
                severity=_severity(snapshot.attrition_risk),
                message=(
                    f"{employee.full_name} has elevated attrition risk. Schedule a retention check-in within 7 days."
                ),
                evidence=(
                    f"Attrition risk={snapshot.attrition_risk}, engagement={snapshot.engagement_score}, sentiment={snapshot.sentiment_score}."
                ),
            )
            created_or_updated.append(nudge)

        if snapshot.burnout_risk >= settings.nudge_threshold_burnout:
            nudge = _create_or_update_nudge(
                db=db,
                employee_id=employee.id,
                nudge_type="burnout_risk",
                severity=_severity(snapshot.burnout_risk),
                message=(
                    f"{employee.full_name} shows burnout risk. Recommend workload rebalance and manager 1:1."
                ),
                evidence=(
                    f"Burnout risk={snapshot.burnout_risk}, overtime={snapshot.overtime_hours}, meetings={snapshot.meeting_hours}."
                ),
            )
            created_or_updated.append(nudge)

    db.commit()
    return created_or_updated
