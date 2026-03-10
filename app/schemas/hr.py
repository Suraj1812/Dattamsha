from datetime import date, datetime

from pydantic import BaseModel, Field


class EmployeeBase(BaseModel):
    external_id: str
    full_name: str
    email: str
    manager_id: int | None = None
    department: str
    role: str
    location: str
    hire_date: date
    employment_status: str = "active"
    base_salary: float = 0


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeRead(EmployeeBase):
    id: int

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    employee: EmployeeRead
    engagement_score: float | None = None
    sentiment_score: float | None = None
    overtime_hours: float | None = None
    meeting_hours: float | None = None
    performance_rating: float | None = None
    goal_completion_pct: float | None = None
    attrition_risk: float | None = None
    burnout_risk: float | None = None


class OrgHealthResponse(BaseModel):
    active_headcount: int
    average_engagement: float
    average_sentiment: float
    high_attrition_risk_count: int
    high_burnout_risk_count: int


class RiskRecord(BaseModel):
    employee_id: int
    employee_name: str
    department: str
    attrition_risk: float
    burnout_risk: float


class NudgeRead(BaseModel):
    id: int
    employee_id: int
    nudge_type: str
    severity: str
    message: str
    evidence: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HiringSimulationRequest(BaseModel):
    planned_hires: int = Field(ge=0)
    avg_salary: float = Field(gt=0)
    expected_revenue_per_hire: float = Field(gt=0)
    expected_time_to_productivity_months: int = Field(ge=0, le=24)


class HiringSimulationResponse(BaseModel):
    annual_hiring_cost: float
    annual_revenue_uplift: float
    net_impact_year_1: float
    payback_months: float


class PolicyQueryRequest(BaseModel):
    question: str


class PolicyQueryResponse(BaseModel):
    answer: str
    citation: str


class ONAEdgeInput(BaseModel):
    source_employee_id: int
    target_employee_id: int
    interaction_count: int = Field(default=1, ge=1)


class ONARequest(BaseModel):
    edges: list[ONAEdgeInput]


class ONAResponse(BaseModel):
    most_central_employee_ids: list[int]
    most_isolated_employee_ids: list[int]
    average_degree: float


class IngestResponse(BaseModel):
    source: str
    employees_loaded: int
    metrics_loaded: int
