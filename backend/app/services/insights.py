from sqlalchemy import String, case, cast, func
from sqlalchemy.orm import Session

from app.models.entities import (
    Employee,
    EmployeeProfileDetails,
    EmployeeRiskSnapshot,
    EngagementMetric,
    PerformanceMetric,
    WorkloadMetric,
)
from app.schemas.hr import (
    EmployeeCreate,
    EmployeeProfileDetailsUpsert,
    EmployeeUpdate,
    OrgHealthResponse,
    ProfileResponse,
    RiskRecord,
)
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
        db.query(Employee, EmployeeRiskSnapshot, EmployeeProfileDetails)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .outerjoin(EmployeeProfileDetails, EmployeeProfileDetails.employee_id == Employee.id)
        .filter(Employee.id == employee_id)
        .first()
    )
    if not row:
        return None

    employee, snapshot, profile_details = row
    if snapshot:
        return ProfileResponse(
            employee=employee,
            profile_details=profile_details,
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
        profile_details=profile_details,
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


def list_risk_records(
    db: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    department: str | None = None,
    min_risk: float | None = None,
) -> list[RiskRecord]:
    query = (
        db.query(
            EmployeeRiskSnapshot.employee_id,
            Employee.full_name,
            Employee.department,
            EmployeeRiskSnapshot.attrition_risk,
            EmployeeRiskSnapshot.burnout_risk,
        )
        .join(Employee, Employee.id == EmployeeRiskSnapshot.employee_id)
        .filter(Employee.employment_status == "active")
    )

    if department:
        query = query.filter(Employee.department == department)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (Employee.full_name.ilike(pattern))
            | (Employee.department.ilike(pattern))
            | (Employee.external_id.ilike(pattern))
            | (cast(Employee.id, String).ilike(pattern))
        )

    if min_risk is not None:
        threshold = max(0.0, min(min_risk, 1.0))
        query = query.filter(
            (EmployeeRiskSnapshot.attrition_risk >= threshold)
            | (EmployeeRiskSnapshot.burnout_risk >= threshold)
        )

    rows = (
        query.order_by(
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


def headcount_by_department(
    db: Session,
    *,
    search: str | None = None,
    department: str | None = None,
) -> dict[str, int]:
    query = db.query(Employee.department, func.count(Employee.id)).filter(
        Employee.employment_status == "active"
    )
    if department:
        query = query.filter(Employee.department == department)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(Employee.department.ilike(pattern))

    rows = query.group_by(Employee.department).all()
    return {department: count for department, count in rows}


def list_employees(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    manager_id: int | None = None,
) -> list[Employee]:
    query = db.query(Employee).filter(Employee.employment_status == "active")
    if manager_id is not None:
        query = query.filter(Employee.manager_id == manager_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (Employee.full_name.ilike(pattern))
            | (Employee.email.ilike(pattern))
            | (Employee.department.ilike(pattern))
            | (Employee.role.ilike(pattern))
            | (Employee.external_id.ilike(pattern))
            | (cast(Employee.id, String).ilike(pattern))
        )

    return (
        query.order_by(Employee.full_name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_manager_reference(db: Session, manager_id: int | None, employee_id: int | None = None) -> None:
    if manager_id is None:
        return
    if employee_id is not None and manager_id == employee_id:
        raise ValueError("manager_id cannot reference the same employee")
    manager = db.query(Employee).filter(Employee.id == manager_id).first()
    if not manager:
        raise ValueError("manager_id references an unknown employee")


def _upsert_employee_profile_details(
    db: Session,
    employee_id: int,
    payload: EmployeeProfileDetailsUpsert,
) -> EmployeeProfileDetails:
    details = db.query(EmployeeProfileDetails).filter(EmployeeProfileDetails.employee_id == employee_id).first()
    if not details:
        details = EmployeeProfileDetails(employee_id=employee_id)
        db.add(details)
        db.flush()

    details.preferred_name = _normalize_optional_text(payload.preferred_name)
    details.phone = _normalize_optional_text(payload.phone)
    details.emergency_contact_name = _normalize_optional_text(payload.emergency_contact_name)
    details.emergency_contact_phone = _normalize_optional_text(payload.emergency_contact_phone)
    details.address = _normalize_optional_text(payload.address)
    details.date_of_birth = payload.date_of_birth
    details.skills = _normalize_optional_text(payload.skills)
    details.bio = _normalize_optional_text(payload.bio)
    details.avatar_image_base64 = _normalize_optional_text(payload.avatar_image_base64)
    return details


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    _validate_manager_reference(db, payload.manager_id)
    employee = Employee(
        external_id=payload.external_id.strip(),
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        manager_id=payload.manager_id,
        department=payload.department.strip(),
        role=payload.role.strip(),
        location=payload.location.strip(),
        hire_date=payload.hire_date,
        employment_status=payload.employment_status.strip().lower(),
        base_salary=payload.base_salary,
    )
    db.add(employee)
    db.flush()
    if payload.profile_details is not None:
        _upsert_employee_profile_details(db, employee.id, payload.profile_details)
    return employee


def update_employee(db: Session, employee_id: int, payload: EmployeeUpdate) -> Employee | None:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    if payload.manager_id is not None:
        _validate_manager_reference(db, payload.manager_id, employee_id=employee_id)
        employee.manager_id = payload.manager_id
    if payload.external_id is not None:
        employee.external_id = payload.external_id.strip()
    if payload.full_name is not None:
        employee.full_name = payload.full_name.strip()
    if payload.email is not None:
        employee.email = payload.email.strip().lower()
    if payload.department is not None:
        employee.department = payload.department.strip()
    if payload.role is not None:
        employee.role = payload.role.strip()
    if payload.location is not None:
        employee.location = payload.location.strip()
    if payload.hire_date is not None:
        employee.hire_date = payload.hire_date
    if payload.employment_status is not None:
        employee.employment_status = payload.employment_status.strip().lower()
    if payload.base_salary is not None:
        employee.base_salary = payload.base_salary
    if payload.profile_details is not None:
        _upsert_employee_profile_details(db, employee.id, payload.profile_details)

    db.flush()
    return employee


def soft_delete_employee(db: Session, employee_id: int) -> Employee | None:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None
    employee.employment_status = "inactive"
    db.flush()
    return employee
