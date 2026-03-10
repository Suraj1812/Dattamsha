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

export type EmployeeProfile = {
  employee: Employee;
  engagement_score: number | null;
  sentiment_score: number | null;
  overtime_hours: number | null;
  meeting_hours: number | null;
  performance_rating: number | null;
  goal_completion_pct: number | null;
  attrition_risk: number | null;
  burnout_risk: number | null;
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

export type PolicyAnswer = {
  answer: string;
  citation: string;
};

export type ErrorShape = {
  error?: {
    type?: string;
    message?: string;
    request_id?: string;
  };
};
