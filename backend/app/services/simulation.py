from sqlalchemy.orm import Session

from app.models.entities import Employee, EmployeeRiskSnapshot
from app.schemas.hr import (
    CompensationSimulationRequest,
    CompensationSimulationResponse,
    HiringSimulationRequest,
    HiringSimulationResponse,
)


def run_hiring_simulation(payload: HiringSimulationRequest) -> HiringSimulationResponse:
    annual_hiring_cost = payload.planned_hires * payload.avg_salary * 1.2
    annual_revenue_uplift = payload.planned_hires * payload.expected_revenue_per_hire

    # Discount year-1 value by ramp-up period.
    productivity_factor = max(0.0, 1 - (payload.expected_time_to_productivity_months / 12))
    adjusted_revenue_uplift = annual_revenue_uplift * productivity_factor

    net_impact = adjusted_revenue_uplift - annual_hiring_cost
    monthly_net = net_impact / 12 if net_impact > 0 else 0
    payback_months = annual_hiring_cost / monthly_net if monthly_net > 0 else 0

    return HiringSimulationResponse(
        annual_hiring_cost=round(annual_hiring_cost, 2),
        annual_revenue_uplift=round(adjusted_revenue_uplift, 2),
        net_impact_year_1=round(net_impact, 2),
        payback_months=round(payback_months, 2),
    )


def run_compensation_simulation(
    db: Session,
    payload: CompensationSimulationRequest,
) -> CompensationSimulationResponse:
    query = (
        db.query(Employee, EmployeeRiskSnapshot)
        .outerjoin(EmployeeRiskSnapshot, EmployeeRiskSnapshot.employee_id == Employee.id)
        .filter(Employee.employment_status == "active")
    )
    if payload.department:
        query = query.filter(Employee.department == payload.department)

    rows = query.all()
    impacted_headcount = len(rows)

    current_annual_payroll = 0.0
    baseline_attrition_cost = 0.0
    for employee, snapshot in rows:
        salary = float(employee.base_salary or 0)
        attrition_risk = float(snapshot.attrition_risk) if snapshot else 0.0
        current_annual_payroll += salary
        baseline_attrition_cost += salary * 0.5 * attrition_risk

    incremental_annual_cost = current_annual_payroll * payload.adjustment_pct
    projected_annual_payroll = current_annual_payroll + incremental_annual_cost

    retention_factor = payload.expected_retention_gain_pct * payload.adjustment_pct
    estimated_attrition_cost_reduction = baseline_attrition_cost * retention_factor
    realization_factor = max(0.0, 1 - (payload.months_to_realization / 12))
    year_1_attrition_benefit = estimated_attrition_cost_reduction * realization_factor
    net_year_1_impact = year_1_attrition_benefit - incremental_annual_cost

    return CompensationSimulationResponse(
        impacted_headcount=impacted_headcount,
        current_annual_payroll=round(current_annual_payroll, 2),
        projected_annual_payroll=round(projected_annual_payroll, 2),
        incremental_annual_cost=round(incremental_annual_cost, 2),
        estimated_attrition_cost_reduction=round(year_1_attrition_benefit, 2),
        net_year_1_impact=round(net_year_1_impact, 2),
    )
