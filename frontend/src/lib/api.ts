import { appConfig } from "@/lib/config";
import type {
  AuthConfig,
  AuthContext,
  AuthAdminPasswordResetRequest,
  AuthLoginRequest,
  AuthPasswordChangeRequest,
  AuthRoleUpdateRequest,
  AuthTokenResponse,
  AuthUser,
  AuthUserCreateRequest,
  CohortAnalytics,
  CompensationSimulationRequest,
  CompensationSimulationResponse,
  EmployeeCreateRequest,
  EmployeeDeleteResponse,
  EmployeeSummary,
  EmployeeTimeline,
  EmployeeProfile,
  EmployeeUpdateRequest,
  ErrorShape,
  HiringSimulationRequest,
  HiringSimulationResponse,
  IngestionRun,
  ManagerTeamOverview,
  Nudge,
  NudgeDispatchRequest,
  NudgeDispatchResponse,
  NudgeFeedback,
  NudgeFeedbackCreate,
  ONAResult,
  OrgHealth,
  PolicyAnswer,
  RiskAnomalyResponse,
  RiskRecord,
  RiskTrendPoint,
  WorkforceFinance,
  WorkforceIngestResponse,
} from "@/lib/types";

type ApiRuntimeContext = {
  apiKey?: string;
  accessToken?: string;
  refreshToken?: string;
  userRole?: string;
  onAuthTokensChange?: (tokens: { accessToken: string; refreshToken: string } | null) => void;
};

const runtimeContext: ApiRuntimeContext = {};
let refreshInFlight: Promise<AuthTokenResponse | null> | null = null;

export class ApiError extends Error {
  status: number;
  requestId?: string;

  constructor(message: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

export function setApiRuntimeContext(next: ApiRuntimeContext): void {
  runtimeContext.apiKey = next.apiKey;
  runtimeContext.accessToken = next.accessToken;
  runtimeContext.refreshToken = next.refreshToken;
  runtimeContext.userRole = next.userRole;
  runtimeContext.onAuthTokensChange = next.onAuthTokensChange;
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  const asString = query.toString();
  return asString ? `?${asString}` : "";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  apiKey?: string,
  allowTokenRefresh = true,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const key = (apiKey ?? runtimeContext.apiKey)?.trim();
  if (key) {
    headers.set("X-API-Key", key);
  }
  const accessToken = runtimeContext.accessToken?.trim();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const role = runtimeContext.userRole?.trim();
  if (!accessToken && role) {
    headers.set("X-User-Role", role);
  }

  try {
    const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    const text = await response.text();
    const data = text ? (JSON.parse(text) as unknown) : null;

    if (!response.ok) {
      if (
        response.status === 401 &&
        allowTokenRefresh &&
        runtimeContext.refreshToken &&
        !path.startsWith("/auth/login") &&
        !path.startsWith("/auth/refresh")
      ) {
        const refreshed = await refreshTokens(apiKey);
        if (refreshed) {
          return request<T>(path, options, apiKey, false);
        }
      }
      const errorPayload = data as ErrorShape;
      const message = errorPayload?.error?.message || `Request failed with ${response.status}`;
      const requestId = errorPayload?.error?.request_id;
      throw new ApiError(message, response.status, requestId);
    }

    return data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("Request timeout. Please try again.", 408);
    }

    throw new ApiError("Network error. Backend might be unavailable.", 503);
  } finally {
    clearTimeout(timeout);
  }
}

async function refreshTokens(apiKey?: string): Promise<AuthTokenResponse | null> {
  if (!runtimeContext.refreshToken) {
    return null;
  }
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    const headers = new Headers();
    headers.set("Content-Type", "application/json");
    const key = (apiKey ?? runtimeContext.apiKey)?.trim();
    if (key) {
      headers.set("X-API-Key", key);
    }

    const response = await fetch(`${appConfig.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      headers,
      body: JSON.stringify({ refresh_token: runtimeContext.refreshToken }),
    });
    if (!response.ok) {
      runtimeContext.onAuthTokensChange?.(null);
      return null;
    }
    const data = (await response.json()) as AuthTokenResponse;
    runtimeContext.accessToken = data.access_token;
    runtimeContext.refreshToken = data.refresh_token;
    runtimeContext.onAuthTokensChange?.({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    });
    return data;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  authConfig: () => request<AuthConfig>("/auth/config"),
  login: (payload: AuthLoginRequest) =>
    request<AuthTokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refresh: (refreshToken: string) =>
    request<AuthTokenResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  logout: (refreshToken: string) =>
    request<{ status: string }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  authMe: (apiKey?: string) => request<AuthContext>("/auth/me", {}, apiKey),
  authUsers: (apiKey?: string) => request<AuthUser[]>("/auth/users", {}, apiKey),
  createAuthUser: (payload: AuthUserCreateRequest, apiKey?: string) =>
    request<AuthUser>(
      "/auth/users",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      apiKey,
    ),
  updateAuthUserRole: (userId: number, payload: AuthRoleUpdateRequest, apiKey?: string) =>
    request<AuthUser>(
      `/auth/users/${userId}/role`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
      apiKey,
    ),
  changePassword: (payload: AuthPasswordChangeRequest, apiKey?: string) =>
    request<{ status: string }>(
      "/auth/change-password",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      apiKey,
    ),
  resetAuthUserPassword: (
    userId: number,
    payload: AuthAdminPasswordResetRequest,
    apiKey?: string,
  ) =>
    request<AuthUser>(
      `/auth/users/${userId}/reset-password`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      apiKey,
    ),
  ingestWorkforce: (payload: Record<string, unknown>, apiKey?: string) =>
    request<WorkforceIngestResponse>("/ingest/workforce", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  orgHealth: (apiKey?: string) => request<OrgHealth>("/insights/org-health", {}, apiKey),
  risks: (
    params: {
      limit?: number;
      offset?: number;
      search?: string;
      department?: string;
      minRisk?: number;
    } = {},
    apiKey?: string,
  ) =>
    request<RiskRecord[]>(
      `/insights/risks${buildQuery({
        limit: params.limit ?? 20,
        offset: params.offset ?? 0,
        search: params.search,
        department: params.department,
        min_risk: params.minRisk,
      })}`,
      {},
      apiKey,
    ),
  riskTrends: (
    params: { days?: number; searchDate?: string } = {},
    apiKey?: string,
  ) =>
    request<RiskTrendPoint[]>(
      `/insights/trends${buildQuery({
        days: params.days ?? 90,
        search_date: params.searchDate,
      })}`,
      {},
      apiKey,
    ),
  cohortAnalytics: (
    params: {
      dimension?: "department" | "location" | "manager";
      search?: string;
    } = {},
    apiKey?: string,
  ) =>
    request<CohortAnalytics>(
      `/insights/cohorts${buildQuery({
        dimension: params.dimension ?? "department",
        search: params.search,
      })}`,
      {},
      apiKey,
    ),
  riskAnomalies: (
    params: {
      dimension?: "department" | "location" | "manager";
      minPopulation?: number;
      search?: string;
      severity?: "all" | "high" | "medium" | "low";
    } = {},
    apiKey?: string,
  ) =>
    request<RiskAnomalyResponse>(
      `/insights/anomalies${buildQuery({
        dimension: params.dimension ?? "department",
        min_population: params.minPopulation ?? 3,
        search: params.search,
        severity: params.severity ?? "all",
      })}`,
      {},
      apiKey,
    ),
  headcountByDepartment: (
    params: { search?: string; department?: string } = {},
    apiKey?: string,
  ) =>
    request<Record<string, number>>(
      `/insights/headcount-by-department${buildQuery({
        search: params.search,
        department: params.department,
      })}`,
      {},
      apiKey,
    ),
  ona: (params: { search?: string } = {}, apiKey?: string) =>
    request<ONAResult>(
      `/insights/ona-from-db${buildQuery({
        search: params.search,
      })}`,
      {},
      apiKey,
    ),
  nudges: (
    params: {
      status?: "open" | "resolved" | "all";
      limit?: number;
      offset?: number;
      search?: string;
      severity?: "all" | "high" | "medium" | "low";
      nudgeType?: string;
      employeeId?: number;
    } = {},
    apiKey?: string,
  ) =>
    request<Nudge[]>(
      `/nudges${buildQuery({
        status: params.status ?? "open",
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
        search: params.search,
        severity: params.severity ?? "all",
        nudge_type: params.nudgeType,
        employee_id: params.employeeId,
      })}`,
      {},
      apiKey,
    ),
  generateNudges: (apiKey?: string) => request<Nudge[]>("/nudges/generate", { method: "POST" }, apiKey),
  resolveNudge: (id: number, apiKey?: string) => request<Nudge>(`/nudges/${id}/resolve`, { method: "POST" }, apiKey),
  dispatchNudges: (payload: NudgeDispatchRequest, apiKey?: string) =>
    request<NudgeDispatchResponse>("/nudges/dispatch", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  nudgeFeedback: (
    id: number,
    params: { search?: string; rating?: number } = {},
    apiKey?: string,
  ) =>
    request<NudgeFeedback[]>(
      `/nudges/${id}/feedback${buildQuery({
        search: params.search,
        rating: params.rating,
      })}`,
      {},
      apiKey,
    ),
  createNudgeFeedback: (id: number, payload: NudgeFeedbackCreate, apiKey?: string) =>
    request<NudgeFeedback>(`/nudges/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  employees: (
    params: { search?: string; managerId?: number; limit?: number; offset?: number } = {},
    apiKey?: string,
  ) =>
    request<EmployeeSummary[]>(
      `/employees${buildQuery({
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
        search: params.search,
        manager_id: params.managerId,
      })}`,
      {},
      apiKey,
    ),
  createEmployee: (payload: EmployeeCreateRequest, apiKey?: string) =>
    request<EmployeeProfile["employee"]>("/employees", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  updateEmployee: (employeeId: number, payload: EmployeeUpdateRequest, apiKey?: string) =>
    request<EmployeeProfile["employee"]>(`/employees/${employeeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, apiKey),
  deleteEmployee: (employeeId: number, apiKey?: string) =>
    request<EmployeeDeleteResponse>(`/employees/${employeeId}`, {
      method: "DELETE",
    }, apiKey),
  employeeProfile: (employeeId: number, apiKey?: string) =>
    request<EmployeeProfile>(`/employees/${employeeId}/profile`, {}, apiKey),
  employeeTimeline: (
    employeeId: number,
    params: {
      days?: number;
      limit?: number;
      searchDate?: string;
      riskBand?: "all" | "high" | "medium" | "low";
    } = {},
    apiKey?: string,
  ) =>
    request<EmployeeTimeline>(
      `/employees/${employeeId}/timeline${buildQuery({
        days: params.days ?? 180,
        limit: params.limit ?? 90,
        search_date: params.searchDate,
        risk_band: params.riskBand ?? "all",
      })}`,
      {},
      apiKey,
    ),
  managerTeamOverview: (
    managerId: number,
    params: { memberSearch?: string; riskBand?: "all" | "high" | "medium" | "low" } = {},
    apiKey?: string,
  ) =>
    request<ManagerTeamOverview>(
      `/managers/${managerId}/team-overview${buildQuery({
        member_search: params.memberSearch,
        risk_band: params.riskBand ?? "all",
      })}`,
      {},
      apiKey,
    ),
  simulateHiring: (payload: HiringSimulationRequest, apiKey?: string) =>
    request<HiringSimulationResponse>("/simulations/hiring-impact", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  simulateCompensation: (payload: CompensationSimulationRequest, apiKey?: string) =>
    request<CompensationSimulationResponse>("/simulations/compensation-adjustment", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  workforceFinance: (params: { annualRevenue?: number; departmentSearch?: string } = {}, apiKey?: string) =>
    request<WorkforceFinance>(
      `/analytics/workforce-finance${buildQuery({
        annual_revenue: params.annualRevenue && params.annualRevenue > 0 ? params.annualRevenue : undefined,
        department_search: params.departmentSearch,
      })}`,
      {},
      apiKey,
    ),
  ingestionRuns: (
    params: {
      search?: string;
      status?: "all" | "success" | "failed";
      limit?: number;
      offset?: number;
    } = {},
    apiKey?: string,
  ) =>
    request<IngestionRun[]>(
      `/ingest/runs${buildQuery({
        search: params.search,
        status: params.status ?? "all",
        limit: params.limit ?? 20,
        offset: params.offset ?? 0,
      })}`,
      {},
      apiKey,
    ),
  policyQuery: (question: string, apiKey?: string) =>
    request<PolicyAnswer>("/assistant/policy-query", {
      method: "POST",
      body: JSON.stringify({ question }),
    }, apiKey),
};
