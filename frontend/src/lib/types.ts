export type OrgHealth = {
  active_headcount: number;
  average_engagement: number;
  average_sentiment: number;
  high_attrition_risk_count: number;
  high_burnout_risk_count: number;
};

export type RiskRecord = {
  employee_id: number;
  employee_name: string;
  department: string;
  attrition_risk: number;
  burnout_risk: number;
};

export type RiskTrendPoint = {
  snapshot_date: string;
  active_headcount: number;
  average_engagement: number;
  average_attrition_risk: number;
  average_burnout_risk: number;
};

export type CohortMetric = {
  cohort: string;
  headcount: number;
  avg_engagement: number;
  avg_attrition_risk: number;
  avg_burnout_risk: number;
  high_attrition_count: number;
  high_burnout_count: number;
};

export type CohortAnalytics = {
  dimension: "department" | "location" | "manager" | string;
  cohorts: CohortMetric[];
};

export type RiskAnomaly = {
  cohort: string;
  metric: "attrition_risk" | "burnout_risk" | string;
  value: number;
  baseline: number;
  delta: number;
  severity: "low" | "medium" | "high" | string;
};

export type RiskAnomalyResponse = {
  dimension: "department" | "location" | "manager" | string;
  anomalies: RiskAnomaly[];
};

export type Employee = {
  id: number;
  external_id: string;
  full_name: string;
  email: string;
  manager_id: number | null;
  department: string;
  role: string;
  location: string;
  hire_date: string;
  employment_status: string;
  base_salary: number;
};

export type EmployeeProfileDetails = {
  employee_id: number;
  preferred_name: string | null;
  phone: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  address: string | null;
  date_of_birth: string | null;
  skills: string | null;
  bio: string | null;
  avatar_image_base64: string | null;
  created_at: string;
  updated_at: string;
};

export type EmployeeSummary = {
  id: number;
  full_name: string;
  department: string;
  role: string;
  manager_id: number | null;
};

export type EmployeeProfile = {
  employee: Employee;
  profile_details: EmployeeProfileDetails | null;
  engagement_score: number | null;
  sentiment_score: number | null;
  overtime_hours: number | null;
  meeting_hours: number | null;
  performance_rating: number | null;
  goal_completion_pct: number | null;
  attrition_risk: number | null;
  burnout_risk: number | null;
};

export type EmployeeProfileDetailsUpsert = {
  preferred_name?: string | null;
  phone?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  address?: string | null;
  date_of_birth?: string | null;
  skills?: string | null;
  bio?: string | null;
  avatar_image_base64?: string | null;
};

export type EmployeeCreateRequest = {
  external_id: string;
  full_name: string;
  email: string;
  manager_id?: number | null;
  department: string;
  role: string;
  location: string;
  hire_date: string;
  employment_status: string;
  base_salary: number;
  profile_details?: EmployeeProfileDetailsUpsert | null;
};

export type EmployeeUpdateRequest = {
  external_id?: string;
  full_name?: string;
  email?: string;
  manager_id?: number | null;
  department?: string;
  role?: string;
  location?: string;
  hire_date?: string;
  employment_status?: string;
  base_salary?: number;
  profile_details?: EmployeeProfileDetailsUpsert | null;
};

export type EmployeeDeleteResponse = {
  status: "deleted";
  employee_id: number;
};

export type EmployeeTimelinePoint = {
  snapshot_date: string;
  engagement_score: number | null;
  sentiment_score: number | null;
  overtime_hours: number | null;
  meeting_hours: number | null;
  after_hours_messages: number | null;
  performance_rating: number | null;
  goal_completion_pct: number | null;
  attrition_risk: number | null;
  burnout_risk: number | null;
};

export type EmployeeTimeline = {
  employee_id: number;
  points: EmployeeTimelinePoint[];
};

export type Nudge = {
  id: number;
  employee_id: number;
  nudge_type: string;
  severity: "low" | "medium" | "high" | string;
  message: string;
  evidence: string;
  status: "open" | "resolved" | string;
  created_at: string;
};

export type NudgeDispatchRequest = {
  channel: "console" | "webhook";
  webhook_url?: string;
  max_items?: number;
  include_resolved?: boolean;
};

export type NudgeDispatchItem = {
  nudge_id: number;
  channel: string;
  status: string;
  response_code: number | null;
  error_message: string | null;
};

export type NudgeDispatchResponse = {
  attempted: number;
  sent: number;
  failed: number;
  items: NudgeDispatchItem[];
};

export type NudgeFeedbackCreate = {
  manager_identifier: string;
  action_taken: string;
  effectiveness_rating: number;
  notes?: string;
};

export type NudgeFeedback = {
  id: number;
  nudge_id: number;
  manager_identifier: string;
  action_taken: string;
  effectiveness_rating: number;
  notes: string | null;
  created_at: string;
};

export type ONAResult = {
  most_central_employee_ids: number[];
  most_isolated_employee_ids: number[];
  average_degree: number;
};

export type HiringSimulationRequest = {
  planned_hires: number;
  avg_salary: number;
  expected_revenue_per_hire: number;
  expected_time_to_productivity_months: number;
};

export type HiringSimulationResponse = {
  annual_hiring_cost: number;
  annual_revenue_uplift: number;
  net_impact_year_1: number;
  payback_months: number;
};

export type CompensationSimulationRequest = {
  department?: string;
  adjustment_pct: number;
  expected_retention_gain_pct: number;
  months_to_realization: number;
};

export type CompensationSimulationResponse = {
  impacted_headcount: number;
  current_annual_payroll: number;
  projected_annual_payroll: number;
  incremental_annual_cost: number;
  estimated_attrition_cost_reduction: number;
  net_year_1_impact: number;
};

export type ManagerTeamMember = {
  employee_id: number;
  full_name: string;
  department: string;
  role: string;
  engagement_score: number | null;
  attrition_risk: number;
  burnout_risk: number;
  open_nudges: number;
};

export type ManagerTeamOverview = {
  manager_id: number;
  manager_name: string;
  team_size: number;
  average_engagement: number;
  average_attrition_risk: number;
  average_burnout_risk: number;
  open_nudges: number;
  recommended_actions: string[];
  members: ManagerTeamMember[];
};

export type DepartmentFinanceMetric = {
  department: string;
  headcount: number;
  annual_payroll: number;
  estimated_attrition_cost: number;
  estimated_burnout_cost: number;
};

export type WorkforceFinance = {
  active_headcount: number;
  annual_payroll: number;
  estimated_attrition_cost: number;
  estimated_burnout_cost: number;
  total_people_risk_cost: number;
  salary_to_revenue_ratio: number | null;
  departments: DepartmentFinanceMetric[];
};

export type IngestionRun = {
  id: number;
  source: string;
  records_received: number;
  employees_upserted: number;
  metrics_upserted: number;
  edges_upserted: number;
  status: string;
  details: string | null;
  created_at: string;
};

export type WorkforceIngestResponse = {
  run_id: number;
  source: string;
  records_received: number;
  employees_upserted: number;
  metrics_upserted: number;
  edges_upserted: number;
  snapshots_refreshed: number;
};

export type PolicyAnswer = {
  answer: string;
  citation: string;
};

export type UserRole = "admin" | "hr_admin" | "manager" | "analyst" | "employee";

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
};

export type RolePermissions = {
  role: string;
  permissions: string[];
};

export type AuthContext = {
  role: string;
  permissions: string[];
  available_roles: string[];
  role_permissions: RolePermissions[];
  auth_type: string;
  is_authenticated: boolean;
  user: AuthUser | null;
};

export type AuthConfig = {
  require_authentication: boolean;
  require_api_key: boolean;
  auth_allow_self_signup: boolean;
};

export type AuthLoginRequest = {
  email: string;
  password: string;
};

export type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
  role: string;
  permissions: string[];
};

export type AuthRoleUpdateRequest = {
  role: UserRole;
};

export type AuthUserCreateRequest = {
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
  is_active?: boolean;
};

export type AuthPasswordChangeRequest = {
  current_password: string;
  new_password: string;
};

export type AuthAdminPasswordResetRequest = {
  new_password: string;
};

export type ErrorShape = {
  error?: {
    type?: string;
    message?: string;
    request_id?: string;
  };
};
