from app.schemas.hr import HiringSimulationRequest, HiringSimulationResponse


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
