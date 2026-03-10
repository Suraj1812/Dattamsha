from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    profile_details: "EmployeeProfileDetailsUpsert | None" = None


class EmployeeUpdate(BaseModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    manager_id: int | None = Field(default=None, ge=1)
    department: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=120)
    hire_date: date | None = None
    employment_status: str | None = Field(default=None, min_length=1, max_length=60)
    base_salary: float | None = Field(default=None, ge=0)
    profile_details: "EmployeeProfileDetailsUpsert | None" = None


class EmployeeRead(EmployeeBase):
    id: int

    model_config = {"from_attributes": True}


class EmployeeProfileDetailsBase(BaseModel):
    preferred_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    skills: str | None = Field(default=None, max_length=2000)
    bio: str | None = Field(default=None, max_length=4000)
    avatar_image_base64: str | None = Field(default=None, max_length=600000)

    @field_validator(
        "preferred_name",
        "phone",
        "emergency_contact_name",
        "emergency_contact_phone",
        "address",
        "skills",
        "bio",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("avatar_image_base64", mode="before")
    @classmethod
    def validate_avatar_data_uri(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.startswith("data:image/") or ";base64," not in normalized:
            raise ValueError("avatar_image_base64 must be a valid data:image/*;base64 URL")
        return normalized


class EmployeeProfileDetailsUpsert(EmployeeProfileDetailsBase):
    pass


class EmployeeProfileDetailsRead(EmployeeProfileDetailsBase):
    employee_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmployeeSummary(BaseModel):
    id: int
    full_name: str
    department: str
    role: str
    manager_id: int | None

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    employee: EmployeeRead
    profile_details: EmployeeProfileDetailsRead | None = None
    engagement_score: float | None = None
    sentiment_score: float | None = None
    overtime_hours: float | None = None
    meeting_hours: float | None = None
    performance_rating: float | None = None
    goal_completion_pct: float | None = None
    attrition_risk: float | None = None
    burnout_risk: float | None = None


class EmployeeDeleteResponse(BaseModel):
    status: Literal["deleted"]
    employee_id: int


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


class RiskTrendPoint(BaseModel):
    snapshot_date: date
    active_headcount: int
    average_engagement: float
    average_attrition_risk: float
    average_burnout_risk: float


class CohortMetric(BaseModel):
    cohort: str
    headcount: int
    avg_engagement: float
    avg_attrition_risk: float
    avg_burnout_risk: float
    high_attrition_count: int
    high_burnout_count: int


class CohortAnalyticsResponse(BaseModel):
    dimension: str
    cohorts: list[CohortMetric]


class RiskAnomaly(BaseModel):
    cohort: str
    metric: Literal["attrition_risk", "burnout_risk"]
    value: float
    baseline: float
    delta: float
    severity: Literal["low", "medium", "high"]


class RiskAnomalyResponse(BaseModel):
    dimension: str
    anomalies: list[RiskAnomaly]


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


class NudgeCountResponse(BaseModel):
    total: int


class NudgeDispatchRequest(BaseModel):
    channel: Literal["console", "webhook"]
    webhook_url: str | None = None
    max_items: int = Field(default=100, ge=1, le=1000)
    include_resolved: bool = False


class NudgeDispatchItem(BaseModel):
    nudge_id: int
    channel: str
    status: str
    response_code: int | None = None
    error_message: str | None = None


class NudgeDispatchResponse(BaseModel):
    attempted: int
    sent: int
    failed: int
    items: list[NudgeDispatchItem]


class NudgeDispatchLogRead(BaseModel):
    id: int
    nudge_id: int
    channel: str
    status: str
    response_code: int | None
    error_message: str | None
    dispatched_at: datetime

    model_config = {"from_attributes": True}


class NudgeFeedbackCreate(BaseModel):
    manager_identifier: str = Field(min_length=1, max_length=120)
    action_taken: str = Field(min_length=3, max_length=2000)
    effectiveness_rating: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=4000)


class NudgeFeedbackRead(BaseModel):
    id: int
    nudge_id: int
    manager_identifier: str
    action_taken: str
    effectiveness_rating: int
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeConsentUpsert(BaseModel):
    consent_type: str = Field(min_length=1, max_length=60)
    status: Literal["granted", "revoked", "expired"]
    source: str = Field(default="system", min_length=1, max_length=80)
    expires_at: datetime | None = None
    details: str | None = Field(default=None, max_length=4000)


class EmployeeConsentRead(BaseModel):
    id: int
    employee_id: int
    consent_type: str
    status: str
    source: str
    captured_at: datetime
    expires_at: datetime | None
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventRead(BaseModel):
    id: int
    action: str
    resource: str
    outcome: str
    actor: str
    request_id: str | None
    details: str | None
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


class CompensationSimulationRequest(BaseModel):
    department: str | None = None
    adjustment_pct: float = Field(ge=-0.5, le=1)
    expected_retention_gain_pct: float = Field(default=0.05, ge=0, le=1)
    months_to_realization: int = Field(default=3, ge=0, le=24)


class CompensationSimulationResponse(BaseModel):
    impacted_headcount: int
    current_annual_payroll: float
    projected_annual_payroll: float
    incremental_annual_cost: float
    estimated_attrition_cost_reduction: float
    net_year_1_impact: float


class PolicyQueryRequest(BaseModel):
    question: str


class PolicyQueryResponse(BaseModel):
    answer: str
    citation: str


class AuthUserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=4000)


class AuthLogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=4000)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserRead
    role: str
    permissions: list[str]


class AuthConfigResponse(BaseModel):
    require_authentication: bool
    require_api_key: bool
    auth_allow_self_signup: bool


class AuthUserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["admin", "hr_admin", "manager", "analyst", "employee"]
    password: str = Field(min_length=8, max_length=256)
    is_active: bool = True


class AuthRoleUpdateRequest(BaseModel):
    role: Literal["admin", "hr_admin", "manager", "analyst", "employee"]


class AuthPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AuthAdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class RolePermissions(BaseModel):
    role: str
    permissions: list[str]


class AccessContextResponse(BaseModel):
    role: str
    permissions: list[str]
    available_roles: list[str]
    role_permissions: list[RolePermissions]
    auth_type: str
    is_authenticated: bool
    user: AuthUserRead | None = None


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


class IngestionRunRead(BaseModel):
    id: int
    source: str
    records_received: int
    employees_upserted: int
    metrics_upserted: int
    edges_upserted: int
    status: str
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeIngestInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    manager_external_id: str | None = Field(default=None, max_length=64)
    department: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=120)
    hire_date: date
    employment_status: str = Field(default="active", min_length=1, max_length=60)
    base_salary: float = Field(default=0, ge=0)


class EngagementMetricIngestInput(BaseModel):
    external_id: str
    snapshot_date: date
    engagement_score: float = Field(ge=0, le=1)
    sentiment_score: float = Field(ge=0, le=1)


class WorkloadMetricIngestInput(BaseModel):
    external_id: str
    snapshot_date: date
    overtime_hours: float = Field(ge=0)
    meeting_hours: float = Field(ge=0)
    after_hours_messages: int = Field(ge=0)


class PerformanceMetricIngestInput(BaseModel):
    external_id: str
    snapshot_date: date
    performance_rating: float = Field(ge=0, le=1)
    goal_completion_pct: float = Field(ge=0, le=1)


class CollaborationEdgeIngestInput(BaseModel):
    source_external_id: str
    target_external_id: str
    interaction_count: int = Field(default=1, ge=1)


class WorkforceIngestRequest(BaseModel):
    source: str = Field(default="api", min_length=1, max_length=80)
    employees: list[EmployeeIngestInput] = Field(default_factory=list)
    engagement_metrics: list[EngagementMetricIngestInput] = Field(default_factory=list)
    workload_metrics: list[WorkloadMetricIngestInput] = Field(default_factory=list)
    performance_metrics: list[PerformanceMetricIngestInput] = Field(default_factory=list)
    collaboration_edges: list[CollaborationEdgeIngestInput] = Field(default_factory=list)


class WorkforceIngestResponse(BaseModel):
    run_id: int
    source: str
    records_received: int
    employees_upserted: int
    metrics_upserted: int
    edges_upserted: int
    snapshots_refreshed: int


class SnapshotRefreshResponse(BaseModel):
    processed_employees: int


class EmployeeTimelinePoint(BaseModel):
    snapshot_date: date
    engagement_score: float | None = None
    sentiment_score: float | None = None
    overtime_hours: float | None = None
    meeting_hours: float | None = None
    after_hours_messages: int | None = None
    performance_rating: float | None = None
    goal_completion_pct: float | None = None
    attrition_risk: float | None = None
    burnout_risk: float | None = None


class EmployeeTimelineResponse(BaseModel):
    employee_id: int
    points: list[EmployeeTimelinePoint]


class ManagerTeamMember(BaseModel):
    employee_id: int
    full_name: str
    department: str
    role: str
    engagement_score: float | None
    attrition_risk: float
    burnout_risk: float
    open_nudges: int


class ManagerTeamOverviewResponse(BaseModel):
    manager_id: int
    manager_name: str
    team_size: int
    average_engagement: float
    average_attrition_risk: float
    average_burnout_risk: float
    open_nudges: int
    recommended_actions: list[str]
    members: list[ManagerTeamMember]


class DepartmentFinanceMetric(BaseModel):
    department: str
    headcount: int
    annual_payroll: float
    estimated_attrition_cost: float
    estimated_burnout_cost: float


class WorkforceFinanceResponse(BaseModel):
    active_headcount: int
    annual_payroll: float
    estimated_attrition_cost: float
    estimated_burnout_cost: float
    total_people_risk_cost: float
    salary_to_revenue_ratio: float | None = None
    departments: list[DepartmentFinanceMetric]
