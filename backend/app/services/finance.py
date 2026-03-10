from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.entities import Employee, EmployeeRiskSnapshot
from app.schemas.hr import DepartmentFinanceMetric, WorkforceFinanceResponse


def get_workforce_finance(
    db: Session,
    *,
    annual_revenue: float | None = None,
    department_search: str | None = None,
) -> WorkforceFinanceResponse:
    rows = (
        db.query(Employee, EmployeeRiskSnapshot)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .filter(Employee.employment_status == "active")
        .all()
    )

    by_department: dict[str, dict[str, float | int]] = defaultdict(lambda: defaultdict(float))
    total_headcount = 0
    total_payroll = 0.0
    total_attrition_cost = 0.0
    total_burnout_cost = 0.0

    for employee, snapshot in rows:
        department = employee.department or "Unknown"
        salary = float(employee.base_salary or 0)
        attrition_risk = float(snapshot.attrition_risk) if snapshot else 0.0
        burnout_risk = float(snapshot.burnout_risk) if snapshot else 0.0

        # Conservative cost estimates: replacement cost and productivity loss.
        attrition_cost = salary * 0.5 * attrition_risk
        burnout_cost = salary * 0.15 * burnout_risk

        by_department[department]["headcount"] += 1
        by_department[department]["payroll"] += salary
        by_department[department]["attrition_cost"] += attrition_cost
        by_department[department]["burnout_cost"] += burnout_cost

        total_headcount += 1
        total_payroll += salary
        total_attrition_cost += attrition_cost
        total_burnout_cost += burnout_cost

    department_rows = [
        DepartmentFinanceMetric(
            department=department,
            headcount=int(values.get("headcount", 0)),
            annual_payroll=round(float(values.get("payroll", 0.0)), 2),
            estimated_attrition_cost=round(float(values.get("attrition_cost", 0.0)), 2),
            estimated_burnout_cost=round(float(values.get("burnout_cost", 0.0)), 2),
        )
        for department, values in by_department.items()
    ]
    if department_search:
        needle = department_search.strip().lower()
        department_rows = [row for row in department_rows if needle in row.department.lower()]
    department_rows.sort(key=lambda row: row.annual_payroll, reverse=True)

    salary_to_revenue_ratio = None
    if annual_revenue is not None and annual_revenue > 0:
        salary_to_revenue_ratio = round(total_payroll / annual_revenue, 4)

    return WorkforceFinanceResponse(
        active_headcount=total_headcount,
        annual_payroll=round(total_payroll, 2),
        estimated_attrition_cost=round(total_attrition_cost, 2),
        estimated_burnout_cost=round(total_burnout_cost, 2),
        total_people_risk_cost=round(total_attrition_cost + total_burnout_cost, 2),
        salary_to_revenue_ratio=salary_to_revenue_ratio,
        departments=department_rows,
    )
