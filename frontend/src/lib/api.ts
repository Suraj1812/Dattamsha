import { appConfig } from "@/lib/config";
import type {
  EmployeeProfile,
  ErrorShape,
  HiringSimulationRequest,
  HiringSimulationResponse,
  Nudge,
  ONAResult,
  OrgHealth,
  PolicyAnswer,
  RiskRecord,
} from "@/lib/types";

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

async function request<T>(
  path: string,
  options: RequestInit = {},
  apiKey?: string,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const key = apiKey?.trim();
  if (key) {
    headers.set("X-API-Key", key);
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

export const api = {
  health: () => request<{ status: string }>("/health"),
  ingestSample: (apiKey?: string) => request<{ source: string; employees_loaded: number; metrics_loaded: number }>("/ingest/sample", { method: "POST" }, apiKey),
  orgHealth: (apiKey?: string) => request<OrgHealth>("/insights/org-health", {}, apiKey),
  risks: (apiKey?: string) => request<RiskRecord[]>("/insights/risks?limit=20", {}, apiKey),
  headcountByDepartment: (apiKey?: string) => request<Record<string, number>>("/insights/headcount-by-department", {}, apiKey),
  ona: (apiKey?: string) => request<ONAResult>("/insights/ona-from-db", {}, apiKey),
  nudges: (apiKey?: string) => request<Nudge[]>("/nudges?status=open", {}, apiKey),
  generateNudges: (apiKey?: string) => request<Nudge[]>("/nudges/generate", { method: "POST" }, apiKey),
  resolveNudge: (id: number, apiKey?: string) => request<Nudge>(`/nudges/${id}/resolve`, { method: "POST" }, apiKey),
  employeeProfile: (employeeId: number, apiKey?: string) =>
    request<EmployeeProfile>(`/employees/${employeeId}/profile`, {}, apiKey),
  simulateHiring: (payload: HiringSimulationRequest, apiKey?: string) =>
    request<HiringSimulationResponse>("/simulations/hiring-impact", {
      method: "POST",
      body: JSON.stringify(payload),
    }, apiKey),
  policyQuery: (question: string, apiKey?: string) =>
    request<PolicyAnswer>("/assistant/policy-query", {
      method: "POST",
      body: JSON.stringify({ question }),
    }, apiKey),
};
