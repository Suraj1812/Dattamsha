import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Bell,
  Bot,
  BriefcaseBusiness,
  CircleAlert,
  LayoutDashboard,
  LogOut,
  RefreshCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NavLink, useNavigate, useParams } from "react-router-dom";

import { MetricCard } from "@/components/MetricCard";
import { Panel } from "@/components/Panel";
import { StatusBanner } from "@/components/StatusBanner";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDashboardData } from "@/hooks/useDashboardData";
import { api, ApiError, setApiRuntimeContext } from "@/lib/api";
import { appConfig } from "@/lib/config";
import { toCompactNumber, toCurrency, toDate, toPercent } from "@/lib/format";
import type {
  AuthUserCreateRequest,
  CompensationSimulationRequest,
  EmployeeCreateRequest,
  EmployeeProfile,
  EmployeeUpdateRequest,
  HiringSimulationRequest,
  NudgeDispatchRequest,
  NudgeFeedbackCreate,
  UserRole,
} from "@/lib/types";
import { useSessionStore } from "@/store/sessionStore";

type ViewTab = "overview" | "alerts" | "employee" | "planning" | "assistant" | "settings";
type TabConfig = {
  key: ViewTab;
  label: string;
  description: string;
  icon: LucideIcon;
  requiredPermissions: string[];
};
type ToastItem = {
  id: number;
  type: "ok" | "error";
  message: string;
};
type EmployeeProfileModalMode = "create" | "edit";
type EmployeeProfileFormState = {
  external_id: string;
  full_name: string;
  email: string;
  manager_id: string;
  department: string;
  role: string;
  location: string;
  hire_date: string;
  employment_status: string;
  base_salary: string;
  preferred_name: string;
  phone: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  address: string;
  date_of_birth: string;
  skills: string;
  bio: string;
  avatar_image_base64: string;
};

const DEFAULT_EMPLOYEE_PROFILE_FORM: EmployeeProfileFormState = {
  external_id: "",
  full_name: "",
  email: "",
  manager_id: "",
  department: "",
  role: "",
  location: "",
  hire_date: new Date().toISOString().slice(0, 10),
  employment_status: "active",
  base_salary: "0",
  preferred_name: "",
  phone: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  address: "",
  date_of_birth: "",
  skills: "",
  bio: "",
  avatar_image_base64: "",
};

const FALLBACK_ROLES: UserRole[] = ["admin", "hr_admin", "manager", "analyst", "employee"];
const ROLE_PERMISSION_MATRIX: Record<UserRole, string[]> = {
  admin: [
    "settings.read",
    "ingest.read",
    "ingest.write",
    "employees.read",
    "employees.write",
    "employees.consent.read",
    "employees.consent.write",
    "insights.read",
    "manager.read",
    "nudges.read",
    "nudges.write",
    "simulations.run",
    "compliance.read",
    "assistant.query",
  ],
  hr_admin: [
    "settings.read",
    "ingest.read",
    "ingest.write",
    "employees.read",
    "employees.write",
    "employees.consent.read",
    "employees.consent.write",
    "insights.read",
    "manager.read",
    "nudges.read",
    "nudges.write",
    "simulations.run",
    "compliance.read",
    "assistant.query",
  ],
  manager: [
    "settings.read",
    "employees.read",
    "employees.consent.read",
    "insights.read",
    "manager.read",
    "nudges.read",
    "nudges.write",
    "simulations.run",
    "assistant.query",
  ],
  analyst: [
    "settings.read",
    "ingest.read",
    "employees.read",
    "insights.read",
    "manager.read",
    "nudges.read",
    "simulations.run",
    "assistant.query",
  ],
  employee: [
    "settings.read",
    "assistant.query",
  ],
};

const CHART_COLORS = ["#3f7af6", "#f2994a", "#2bb673", "#c278e4", "#ef5466", "#2d9cdb"];
const TAB_CONFIG: TabConfig[] = [
  {
    key: "overview",
    label: "Overview",
    description: "Org trends and workforce health",
    icon: LayoutDashboard,
    requiredPermissions: ["insights.read"],
  },
  {
    key: "alerts",
    label: "Team Alerts",
    description: "Manager queue and nudges",
    icon: CircleAlert,
    requiredPermissions: ["manager.read", "nudges.read"],
  },
  {
    key: "employee",
    label: "Employee View",
    description: "Profile and risk timeline",
    icon: Users,
    requiredPermissions: ["employees.read"],
  },
  {
    key: "planning",
    label: "Planning",
    description: "Hiring and compensation simulators",
    icon: BriefcaseBusiness,
    requiredPermissions: ["simulations.run"],
  },
  {
    key: "assistant",
    label: "Policy Assistant",
    description: "Policy Q&A and citations",
    icon: Bot,
    requiredPermissions: ["assistant.query"],
  },
  {
    key: "settings",
    label: "Settings",
    description: "RBAC and access controls",
    icon: ShieldCheck,
    requiredPermissions: ["settings.read"],
  },
];

const VIEW_TABS: ViewTab[] = ["overview", "alerts", "employee", "planning", "assistant", "settings"];

function isViewTab(value: string | undefined): value is ViewTab {
  return VIEW_TABS.includes(value as ViewTab);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}${error.requestId ? ` (request: ${error.requestId})` : ""}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function matchesSearch(
  query: string,
  ...values: Array<string | number | null | undefined>
): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }
  return values.some((value) => String(value ?? "").toLowerCase().includes(normalizedQuery));
}

function normalizeOptionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function mapProfileToForm(profile: EmployeeProfile): EmployeeProfileFormState {
  const details = profile.profile_details;
  return {
    external_id: profile.employee.external_id ?? "",
    full_name: profile.employee.full_name ?? "",
    email: profile.employee.email ?? "",
    manager_id: profile.employee.manager_id != null ? String(profile.employee.manager_id) : "",
    department: profile.employee.department ?? "",
    role: profile.employee.role ?? "",
    location: profile.employee.location ?? "",
    hire_date: profile.employee.hire_date ?? "",
    employment_status: profile.employee.employment_status ?? "active",
    base_salary: String(profile.employee.base_salary ?? 0),
    preferred_name: details?.preferred_name ?? "",
    phone: details?.phone ?? "",
    emergency_contact_name: details?.emergency_contact_name ?? "",
    emergency_contact_phone: details?.emergency_contact_phone ?? "",
    address: details?.address ?? "",
    date_of_birth: details?.date_of_birth ?? "",
    skills: details?.skills ?? "",
    bio: details?.bio ?? "",
    avatar_image_base64: details?.avatar_image_base64 ?? "",
  };
}

function buildEmployeePayloadFromForm(form: EmployeeProfileFormState): EmployeeCreateRequest {
  const managerId = Number(form.manager_id);
  return {
    external_id: form.external_id.trim(),
    full_name: form.full_name.trim(),
    email: form.email.trim(),
    manager_id: form.manager_id.trim() && Number.isFinite(managerId) && managerId > 0 ? managerId : null,
    department: form.department.trim(),
    role: form.role.trim(),
    location: form.location.trim(),
    hire_date: form.hire_date,
    employment_status: form.employment_status.trim() || "active",
    base_salary: Number(form.base_salary) >= 0 ? Number(form.base_salary) : 0,
    profile_details: {
      preferred_name: normalizeOptionalText(form.preferred_name),
      phone: normalizeOptionalText(form.phone),
      emergency_contact_name: normalizeOptionalText(form.emergency_contact_name),
      emergency_contact_phone: normalizeOptionalText(form.emergency_contact_phone),
      address: normalizeOptionalText(form.address),
      date_of_birth: normalizeOptionalText(form.date_of_birth),
      skills: normalizeOptionalText(form.skills),
      bio: normalizeOptionalText(form.bio),
      avatar_image_base64: normalizeOptionalText(form.avatar_image_base64),
    },
  };
}

export default function App() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { tab: tabParam } = useParams<{ tab: string }>();
  const tab: ViewTab = isViewTab(tabParam) ? tabParam : "overview";
  const goToTab = (nextTab: ViewTab): void => {
    navigate(`/dashboard/${nextTab}`);
  };
  const [showFilters, setShowFilters] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const apiKey = useSessionStore((state) => state.apiKey);
  const accessToken = useSessionStore((state) => state.accessToken);
  const refreshToken = useSessionStore((state) => state.refreshToken);
  const userRole = useSessionStore((state) => state.userRole);
  const loginEmail = useSessionStore((state) => state.loginEmail);
  const setApiKey = useSessionStore((state) => state.setApiKey);
  const setUserRole = useSessionStore((state) => state.setUserRole);
  const setLoginEmail = useSessionStore((state) => state.setLoginEmail);
  const setTokens = useSessionStore((state) => state.setTokens);
  const clearTokens = useSessionStore((state) => state.clearTokens);
  const [loginPassword, setLoginPassword] = useState("ChangeMe@123");
  const [newUserInput, setNewUserInput] = useState<AuthUserCreateRequest>({
    email: "",
    full_name: "",
    role: "manager",
    password: "",
    is_active: true,
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
  });
  const [adminResetPasswords, setAdminResetPasswords] = useState<Record<number, string>>({});
  const [employeeId, setEmployeeId] = useState(appConfig.defaultEmployeeId);
  const [employeeProfileModalOpen, setEmployeeProfileModalOpen] = useState(false);
  const [employeeDeleteModalOpen, setEmployeeDeleteModalOpen] = useState(false);
  const [employeeProfileModalMode, setEmployeeProfileModalMode] = useState<EmployeeProfileModalMode>("create");
  const [employeeProfileForm, setEmployeeProfileForm] = useState<EmployeeProfileFormState>(
    { ...DEFAULT_EMPLOYEE_PROFILE_FORM },
  );
  const [managerId, setManagerId] = useState(1);
  const [policyQuestion, setPolicyQuestion] = useState("How many paid leave days are available?");
  const [annualRevenue, setAnnualRevenue] = useState<number>(0);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [hasShownConnectionToast, setHasShownConnectionToast] = useState(false);
  const [rbacPermissionSearch, setRbacPermissionSearch] = useState<string>("");
  const [ingestPayloadText, setIngestPayloadText] = useState<string>(
    JSON.stringify(
      {
        source: "hris-api",
        employees: [],
        engagement_metrics: [],
        workload_metrics: [],
        performance_metrics: [],
        collaboration_edges: [],
      },
      null,
      2,
    ),
  );

  const [simulationInput, setSimulationInput] = useState<HiringSimulationRequest>({
    planned_hires: 6,
    avg_salary: 1200000,
    expected_revenue_per_hire: 2400000,
    expected_time_to_productivity_months: 4,
  });

  const [compensationInput, setCompensationInput] = useState<CompensationSimulationRequest>({
    department: "",
    adjustment_pct: 0.08,
    expected_retention_gain_pct: 0.05,
    months_to_realization: 3,
  });

  const [dispatchInput, setDispatchInput] = useState<NudgeDispatchRequest>({
    channel: "console",
    webhook_url: "",
    max_items: 50,
    include_resolved: false,
  });

  const [feedbackInput, setFeedbackInput] = useState<NudgeFeedbackCreate>({
    manager_identifier: "manager-1",
    action_taken: "Scheduled 1:1 and workload review",
    effectiveness_rating: 4,
    notes: "Initial signs are positive.",
  });
  const [overviewDepartmentFilter, setOverviewDepartmentFilter] = useState<string>("all");
  const [overviewMinRiskFilter, setOverviewMinRiskFilter] = useState<string>("0");
  const [overviewEmployeeSearch, setOverviewEmployeeSearch] = useState<string>("");
  const [departmentSearch, setDepartmentSearch] = useState<string>("");
  const [cohortSearch, setCohortSearch] = useState<string>("");
  const [anomalySearch, setAnomalySearch] = useState<string>("");
  const [anomalySeverityFilter, setAnomalySeverityFilter] = useState<string>("all");
  const [financeSearch, setFinanceSearch] = useState<string>("");
  const [ingestionSearch, setIngestionSearch] = useState<string>("");
  const [ingestionStatusFilter, setIngestionStatusFilter] = useState<string>("all");
  const [teamSearch, setTeamSearch] = useState<string>("");
  const [teamRiskFilter, setTeamRiskFilter] = useState<string>("all");
  const [nudgeSearch, setNudgeSearch] = useState<string>("");
  const [nudgeSeverityFilter, setNudgeSeverityFilter] = useState<string>("all");
  const [feedbackSearch, setFeedbackSearch] = useState<string>("");
  const [feedbackRatingFilter, setFeedbackRatingFilter] = useState<string>("all");
  const [employeeSearch, setEmployeeSearch] = useState<string>("");
  const [timelineSearch, setTimelineSearch] = useState<string>("");
  const [timelineRiskFilter, setTimelineRiskFilter] = useState<string>("all");
  const [planningDepartmentSearch, setPlanningDepartmentSearch] = useState<string>("");
  const [trendSearch, setTrendSearch] = useState<string>("");
  const [trendMetricFilter, setTrendMetricFilter] = useState<string>("all");
  const [networkSearch, setNetworkSearch] = useState<string>("");
  const [assistantHistorySearch, setAssistantHistorySearch] = useState<string>("");
  const [assistantHistory, setAssistantHistory] = useState<
    Array<{ question: string; answer: string; citation: string; createdAt: string }>
  >([]);
  const toastTimeoutRef = useRef<Map<number, number>>(new Map());
  const toastDedupRef = useRef<Map<string, number>>(new Map());
  const toastCounterRef = useRef(0);
  const notificationMenuRef = useRef<HTMLDivElement | null>(null);

  const dismissToast = useCallback((toastId: number): void => {
    const timerId = toastTimeoutRef.current.get(toastId);
    if (timerId) {
      window.clearTimeout(timerId);
      toastTimeoutRef.current.delete(toastId);
    }
    setToasts((previous) => previous.filter((toast) => toast.id !== toastId));
  }, []);

  const pushToast = useCallback((type: ToastItem["type"], message: string, durationMs = 2000): void => {
    const normalizedMessage = message.trim();
    if (!normalizedMessage) {
      return;
    }
    const dedupeKey = `${type}:${normalizedMessage}`;
    const now = Date.now();
    const lastShownAt = toastDedupRef.current.get(dedupeKey) ?? 0;
    if (now - lastShownAt < 1200) {
      return;
    }
    toastDedupRef.current.set(dedupeKey, now);
    const id = ++toastCounterRef.current;
    setToasts((previous) => [...previous, { id, type, message: normalizedMessage }]);
    const effectiveDurationMs = Math.max(400, Math.min(durationMs, 2000));
    const timerId = window.setTimeout(() => {
      dismissToast(id);
    }, effectiveDurationMs);
    toastTimeoutRef.current.set(id, timerId);
  }, [dismissToast]);

  useEffect(() => {
    const activeToastTimeouts = toastTimeoutRef.current;
    return () => {
      activeToastTimeouts.forEach((timerId) => window.clearTimeout(timerId));
      activeToastTimeouts.clear();
    };
  }, []);

  useEffect(() => {
    if (!showNotifications) {
      return;
    }
    const handlePointerDown = (event: PointerEvent): void => {
      if (!notificationMenuRef.current) {
        return;
      }
      if (event.target instanceof Node && !notificationMenuRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    const handleEscape = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        setShowNotifications(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [showNotifications]);

  const authConfig = useQuery({
    queryKey: ["authConfig"],
    queryFn: () => api.authConfig(),
    retry: 1,
    staleTime: 60_000,
  });
  const isAuthRequired = authConfig.data?.require_authentication ?? false;
  const isLoggedIn = Boolean(accessToken);
  const effectiveRole: UserRole = isAuthRequired && !isLoggedIn ? "employee" : userRole;

  const data = useDashboardData(apiKey, effectiveRole);
  const debouncedOverviewEmployeeSearch = useDebouncedValue(overviewEmployeeSearch);
  const debouncedDepartmentSearch = useDebouncedValue(departmentSearch);
  const debouncedCohortSearch = useDebouncedValue(cohortSearch);
  const debouncedAnomalySearch = useDebouncedValue(anomalySearch);
  const debouncedFinanceSearch = useDebouncedValue(financeSearch);
  const debouncedIngestionSearch = useDebouncedValue(ingestionSearch);
  const debouncedTeamSearch = useDebouncedValue(teamSearch);
  const debouncedNudgeSearch = useDebouncedValue(nudgeSearch);
  const debouncedFeedbackSearch = useDebouncedValue(feedbackSearch);
  const debouncedEmployeeSearch = useDebouncedValue(employeeSearch);
  const debouncedTimelineSearch = useDebouncedValue(timelineSearch);
  const debouncedPlanningDepartmentSearch = useDebouncedValue(planningDepartmentSearch);
  const debouncedTrendSearch = useDebouncedValue(trendSearch);
  const debouncedNetworkSearch = useDebouncedValue(networkSearch);
  const debouncedAssistantHistorySearch = useDebouncedValue(assistantHistorySearch);
  const rolePermissions = useMemo(
    () => {
      if (isAuthRequired && !isLoggedIn) {
        return new Set<string>();
      }
      if (isAuthRequired && isLoggedIn) {
        return new Set(ROLE_PERMISSION_MATRIX[userRole] ?? []);
      }
      return new Set(ROLE_PERMISSION_MATRIX[effectiveRole] ?? []);
    },
    [effectiveRole, isAuthRequired, isLoggedIn, userRole],
  );
  const canReadInsights = rolePermissions.has("insights.read");
  const canReadEmployees = rolePermissions.has("employees.read");
  const canReadManager = rolePermissions.has("manager.read");
  const canReadNudges = rolePermissions.has("nudges.read");
  const canReadIngest = rolePermissions.has("ingest.read");
  const canManageUsers = userRole === "admin";

  useEffect(() => {
    setApiRuntimeContext({
      apiKey,
      userRole: !isAuthRequired ? userRole : undefined,
      accessToken: accessToken || undefined,
      refreshToken: refreshToken || undefined,
      onAuthTokensChange: (tokens) => {
        if (!tokens) {
          clearTokens();
          return;
        }
        setTokens(tokens.accessToken, tokens.refreshToken);
      },
    });
  }, [apiKey, userRole, isAuthRequired, accessToken, refreshToken, clearTokens, setTokens]);

  useEffect(() => {
    void queryClient.invalidateQueries();
  }, [queryClient, userRole, accessToken, refreshToken]);

  useEffect(() => {
    const firstEmployeeId = data.employees.data?.[0]?.id;
    if (firstEmployeeId && (!employeeId || employeeId < 1)) {
      setEmployeeId(firstEmployeeId);
    }
  }, [data.employees.data, employeeId]);

  useEffect(() => {
    if (data.health.data?.status === "ok" && !hasShownConnectionToast) {
      pushToast("ok", "Backend connected successfully.");
      setHasShownConnectionToast(true);
    }
  }, [data.health.data?.status, hasShownConnectionToast, pushToast]);

  const employeeProfile = useQuery({
    queryKey: ["employeeProfile", apiKey, employeeId],
    queryFn: () => api.employeeProfile(employeeId, apiKey),
    enabled: canReadEmployees && Number.isFinite(employeeId) && employeeId > 0,
    retry: 1,
  });

  const employeeTimeline = useQuery({
    queryKey: ["employeeTimeline", apiKey, employeeId, debouncedTimelineSearch, timelineRiskFilter],
    queryFn: () =>
      api.employeeTimeline(
        employeeId,
        {
          days: 180,
          limit: 90,
          searchDate: debouncedTimelineSearch || undefined,
          riskBand: timelineRiskFilter as "all" | "high" | "medium" | "low",
        },
        apiKey,
      ),
    enabled: canReadEmployees && Number.isFinite(employeeId) && employeeId > 0,
    retry: 1,
    staleTime: 20_000,
  });

  const managerTeam = useQuery({
    queryKey: ["managerTeam", apiKey, managerId, debouncedTeamSearch, teamRiskFilter],
    queryFn: () =>
      api.managerTeamOverview(
        managerId,
        {
          memberSearch: debouncedTeamSearch || undefined,
          riskBand: teamRiskFilter as "all" | "high" | "medium" | "low",
        },
        apiKey,
      ),
    enabled: canReadManager && Number.isFinite(managerId) && managerId > 0,
    retry: 1,
    staleTime: 20_000,
  });

  const risksQuery = useQuery({
    queryKey: [
      "risksFiltered",
      apiKey,
      overviewDepartmentFilter,
      overviewMinRiskFilter,
      debouncedOverviewEmployeeSearch,
    ],
    queryFn: () =>
      api.risks(
        {
          limit: 200,
          offset: 0,
          search: debouncedOverviewEmployeeSearch || undefined,
          department: overviewDepartmentFilter !== "all" ? overviewDepartmentFilter : undefined,
          minRisk: Number(overviewMinRiskFilter) > 0 ? Number(overviewMinRiskFilter) : undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 20_000,
  });

  const headcountQuery = useQuery({
    queryKey: ["headcountFiltered", apiKey, overviewDepartmentFilter, debouncedDepartmentSearch],
    queryFn: () =>
      api.headcountByDepartment(
        {
          search: debouncedDepartmentSearch || undefined,
          department: overviewDepartmentFilter !== "all" ? overviewDepartmentFilter : undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 30_000,
  });

  const riskTrendsQuery = useQuery({
    queryKey: ["riskTrendsFiltered", apiKey, debouncedTrendSearch],
    queryFn: () =>
      api.riskTrends(
        {
          days: 90,
          searchDate: debouncedTrendSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 30_000,
  });

  const cohortsQuery = useQuery({
    queryKey: ["cohortsFiltered", apiKey, debouncedCohortSearch],
    queryFn: () =>
      api.cohortAnalytics(
        {
          dimension: "department",
          search: debouncedCohortSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 30_000,
  });

  const anomaliesQuery = useQuery({
    queryKey: ["anomaliesFiltered", apiKey, anomalySeverityFilter, debouncedAnomalySearch],
    queryFn: () =>
      api.riskAnomalies(
        {
          dimension: "department",
          minPopulation: 3,
          search: debouncedAnomalySearch || undefined,
          severity: anomalySeverityFilter as "all" | "high" | "medium" | "low",
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 20_000,
  });

  const workforceFinance = useQuery({
    queryKey: ["workforceFinance", apiKey, annualRevenue, debouncedFinanceSearch],
    queryFn: () =>
      api.workforceFinance(
        {
          annualRevenue: annualRevenue > 0 ? annualRevenue : undefined,
          departmentSearch: debouncedFinanceSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 60_000,
  });

  const planningFinance = useQuery({
    queryKey: ["planningFinance", apiKey, annualRevenue, debouncedPlanningDepartmentSearch],
    queryFn: () =>
      api.workforceFinance(
        {
          annualRevenue: annualRevenue > 0 ? annualRevenue : undefined,
          departmentSearch: debouncedPlanningDepartmentSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 60_000,
  });

  const ingestionRunsQuery = useQuery({
    queryKey: ["ingestionRunsFiltered", apiKey, debouncedIngestionSearch, ingestionStatusFilter],
    queryFn: () =>
      api.ingestionRuns(
        {
          limit: 50,
          offset: 0,
          search: debouncedIngestionSearch || undefined,
          status: ingestionStatusFilter as "all" | "success" | "failed",
        },
        apiKey,
      ),
    enabled: canReadIngest,
    retry: 1,
    staleTime: 20_000,
  });

  const nudgesQuery = useQuery({
    queryKey: ["nudgesFiltered", apiKey, debouncedNudgeSearch, nudgeSeverityFilter],
    queryFn: () =>
      api.nudges(
        {
          status: "open",
          limit: 100,
          offset: 0,
          search: debouncedNudgeSearch || undefined,
          severity: nudgeSeverityFilter as "all" | "high" | "medium" | "low",
        },
        apiKey,
      ),
    enabled: canReadNudges,
    retry: 1,
    staleTime: 10_000,
  });
  const notificationFeedQuery = useQuery({
    queryKey: ["notificationFeed", apiKey],
    queryFn: () =>
      api.nudges(
        {
          status: "open",
          limit: 20,
          offset: 0,
          severity: "all",
        },
        apiKey,
      ),
    enabled: canReadNudges,
    retry: 1,
    staleTime: 10_000,
  });
  const nudgeOpenCountQuery = useQuery({
    queryKey: ["nudgeOpenCount", apiKey],
    queryFn: () =>
      api.nudgeCount(
        {
          status: "open",
          severity: "all",
        },
        apiKey,
      ),
    enabled: canReadNudges,
    retry: 1,
    staleTime: 10_000,
  });

  const employeesQuery = useQuery({
    queryKey: ["employeesFiltered", apiKey, debouncedEmployeeSearch],
    queryFn: () =>
      api.employees(
        {
          limit: 100,
          offset: 0,
          search: debouncedEmployeeSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadEmployees,
    retry: 1,
    staleTime: 30_000,
  });

  const createEmployeeMutation = useMutation({
    mutationFn: (payload: EmployeeCreateRequest) => api.createEmployee(payload, apiKey),
    onSuccess: (createdEmployee) => {
      setEmployeeId(createdEmployee.id);
      setEmployeeProfileModalOpen(false);
      setEmployeeProfileForm({ ...DEFAULT_EMPLOYEE_PROFILE_FORM });
      pushToast("ok", "Employee profile created.");
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      pushToast("error", errorMessage(error));
    },
  });

  const updateEmployeeMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: EmployeeUpdateRequest }) =>
      api.updateEmployee(id, payload, apiKey),
    onSuccess: () => {
      setEmployeeProfileModalOpen(false);
      pushToast("ok", "Employee profile updated.");
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      pushToast("error", errorMessage(error));
    },
  });

  const deleteEmployeeMutation = useMutation({
    mutationFn: (id: number) => api.deleteEmployee(id, apiKey),
    onSuccess: () => {
      setEmployeeDeleteModalOpen(false);
      setEmployeeId(0);
      pushToast("ok", "Employee profile deleted.");
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      pushToast("error", errorMessage(error));
    },
  });

  const onaQuery = useQuery({
    queryKey: ["onaFiltered", apiKey, debouncedNetworkSearch],
    queryFn: () =>
      api.ona(
        {
          search: debouncedNetworkSearch || undefined,
        },
        apiKey,
      ),
    enabled: canReadInsights,
    retry: 1,
    staleTime: 30_000,
  });

  const simulateHiringMutation = useMutation({
    mutationFn: (payload: HiringSimulationRequest) => api.simulateHiring(payload, apiKey),
  });

  const simulateCompMutation = useMutation({
    mutationFn: (payload: CompensationSimulationRequest) =>
      api.simulateCompensation(
        {
          ...payload,
          department: payload.department?.trim() ? payload.department : undefined,
        },
        apiKey,
      ),
  });

  const policyMutation = useMutation({
    mutationFn: (question: string) => api.policyQuery(question, apiKey),
    onSuccess: (result, question) => {
      setAssistantHistory((previous) => [
        {
          question,
          answer: result.answer,
          citation: result.citation,
          createdAt: new Date().toISOString(),
        },
        ...previous,
      ]);
    },
  });

  const loginMutation = useMutation({
    mutationFn: () => api.login({ email: loginEmail, password: loginPassword }),
    onSuccess: (result) => {
      setTokens(result.access_token, result.refresh_token);
      const nextRole = FALLBACK_ROLES.includes(result.role as UserRole)
        ? (result.role as UserRole)
        : "employee";
      setUserRole(nextRole);
      pushToast("ok", `Logged in as ${result.user.full_name}`);
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      pushToast("error", errorMessage(error));
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => (refreshToken ? api.logout(refreshToken) : Promise.resolve({ status: "ok" })),
    onSettled: () => {
      clearTokens();
      pushToast("ok", "Logged out.");
      void queryClient.invalidateQueries();
    },
  });

  const generateNudgeMutation = useMutation({
    mutationFn: () => api.generateNudges(apiKey),
    onSuccess: () => {
      pushToast("ok", "Nudges generated.");
      void queryClient.invalidateQueries({ queryKey: ["nudgesFiltered", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["notificationFeed", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["nudgeOpenCount", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["risksFiltered", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["orgHealth", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["managerTeam", apiKey, managerId] });
    },
  });

  const resolveNudgeMutation = useMutation({
    mutationFn: (id: number) => api.resolveNudge(id, apiKey),
    onSuccess: () => {
      pushToast("ok", "Nudge resolved.");
      void queryClient.invalidateQueries({ queryKey: ["nudgesFiltered", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["notificationFeed", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["nudgeOpenCount", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["managerTeam", apiKey, managerId] });
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: (payload: NudgeDispatchRequest) => api.dispatchNudges(payload, apiKey),
    onSuccess: (result) => {
      pushToast("ok", `Dispatch complete. Sent ${result.sent}/${result.attempted}.`);
    },
  });

  const selectedNudgeId = nudgesQuery.data?.[0]?.id ?? 0;
  const nudgeFeedback = useQuery({
    queryKey: ["nudgeFeedback", apiKey, selectedNudgeId, debouncedFeedbackSearch, feedbackRatingFilter],
    queryFn: () =>
      api.nudgeFeedback(
        selectedNudgeId,
        {
          search: debouncedFeedbackSearch || undefined,
          rating: feedbackRatingFilter === "all" ? undefined : Number(feedbackRatingFilter),
        },
        apiKey,
      ),
    enabled: canReadNudges && selectedNudgeId > 0,
    retry: 1,
    staleTime: 20_000,
  });

  const createFeedbackMutation = useMutation({
    mutationFn: (payload: NudgeFeedbackCreate) => api.createNudgeFeedback(selectedNudgeId, payload, apiKey),
    onSuccess: () => {
      pushToast("ok", "Nudge feedback submitted.");
      void queryClient.invalidateQueries({ queryKey: ["nudgeFeedback", apiKey, selectedNudgeId] });
    },
  });

  const ingestMutation = useMutation({
    mutationFn: async () => {
      const payload = JSON.parse(ingestPayloadText) as Record<string, unknown>;
      return api.ingestWorkforce(payload, apiKey);
    },
    onSuccess: (result) => {
      pushToast(
        "ok",
        `Ingestion run #${result.run_id} complete. Employees ${result.employees_upserted}, metrics ${result.metrics_upserted}, snapshots ${result.snapshots_refreshed}.`,
      );
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      pushToast("error", `Ingestion failed: ${errorMessage(error)}`);
    },
  });

  const authContext = useQuery({
    queryKey: ["authContext", apiKey, userRole, accessToken],
    queryFn: () => api.authMe(apiKey),
    enabled: !isAuthRequired || isLoggedIn,
    retry: 1,
    staleTime: 60_000,
  });

  const authUsersQuery = useQuery({
    queryKey: ["authUsers", apiKey, accessToken],
    queryFn: () => api.authUsers(apiKey),
    enabled: canManageUsers && (!isAuthRequired || isLoggedIn),
    retry: 1,
    staleTime: 30_000,
  });

  const createAuthUserMutation = useMutation({
    mutationFn: (payload: AuthUserCreateRequest) => api.createAuthUser(payload, apiKey),
    onSuccess: () => {
      pushToast("ok", "User created.");
      setNewUserInput({
        email: "",
        full_name: "",
        role: "manager",
        password: "",
        is_active: true,
      });
      void queryClient.invalidateQueries({ queryKey: ["authUsers", apiKey] });
    },
  });

  const updateAuthRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: UserRole }) =>
      api.updateAuthUserRole(userId, { role }, apiKey),
    onSuccess: () => {
      pushToast("ok", "User role updated.");
      void queryClient.invalidateQueries({ queryKey: ["authUsers", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["authContext", apiKey] });
    },
  });

  const resetAuthPasswordMutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      api.resetAuthUserPassword(userId, { new_password: newPassword }, apiKey),
    onSuccess: (_, variables) => {
      pushToast("ok", "User password reset.");
      setAdminResetPasswords((previous) => ({ ...previous, [variables.userId]: "" }));
      void queryClient.invalidateQueries({ queryKey: ["authUsers", apiKey] });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: () => api.changePassword(passwordForm, apiKey),
    onSuccess: () => {
      pushToast("ok", "Password updated.");
      setPasswordForm({ current_password: "", new_password: "" });
    },
  });

  useEffect(() => {
    const resolvedRole = authContext.data?.role;
    if (!resolvedRole) {
      return;
    }
    if (FALLBACK_ROLES.includes(resolvedRole as UserRole) && resolvedRole !== userRole) {
      setUserRole(resolvedRole as UserRole);
    }
  }, [authContext.data?.role, userRole, setUserRole]);

  const departmentOptions = useMemo(
    () => Object.keys(data.headcountByDepartment.data ?? {}).sort((a, b) => a.localeCompare(b)),
    [data.headcountByDepartment.data],
  );

  const filteredRisks = useMemo(() => risksQuery.data ?? [], [risksQuery.data]);

  const headcountChartData = useMemo(() => {
    if (!headcountQuery.data) {
      return [];
    }
    return Object.entries(headcountQuery.data)
      .map(([department, count]) => ({
        department,
        count,
      }));
  }, [headcountQuery.data]);

  const riskChartData = useMemo(() => {
    return filteredRisks.slice(0, 8).map((row) => ({
      name: row.employee_name,
      attrition: Number((row.attrition_risk * 100).toFixed(1)),
      burnout: Number((row.burnout_risk * 100).toFixed(1)),
    }));
  }, [filteredRisks]);

  const trendChartData = useMemo(() => {
    return (riskTrendsQuery.data ?? [])
      .slice(-20)
      .map((point) => ({
      date: point.snapshot_date,
      attrition: Number((point.average_attrition_risk * 100).toFixed(1)),
      burnout: Number((point.average_burnout_risk * 100).toFixed(1)),
      engagement: Number((point.average_engagement * 100).toFixed(1)),
      }));
  }, [riskTrendsQuery.data]);

  const filteredCohorts = cohortsQuery.data?.cohorts ?? [];
  const filteredAnomalies = anomaliesQuery.data?.anomalies ?? [];
  const filteredFinanceDepartments = workforceFinance.data?.departments ?? [];
  const filteredIngestionRuns = ingestionRunsQuery.data ?? [];
  const filteredTeamMembers = managerTeam.data?.members ?? [];

  const filteredNudges = useMemo(() => nudgesQuery.data ?? [], [nudgesQuery.data]);
  const filteredFeedback = nudgeFeedback.data ?? [];
  const filteredEmployeeOptions = employeesQuery.data ?? [];
  const filteredTimelinePoints = employeeTimeline.data?.points ?? [];
  const planningDepartmentRows = planningFinance.data?.departments ?? [];

  const filteredAssistantHistory = useMemo(() => {
    return assistantHistory.filter((entry) =>
      matchesSearch(debouncedAssistantHistorySearch, entry.question, entry.answer, entry.citation),
    );
  }, [assistantHistory, debouncedAssistantHistorySearch]);

  const filteredCentralIds = onaQuery.data?.most_central_employee_ids ?? [];
  const filteredIsolatedIds = onaQuery.data?.most_isolated_employee_ids ?? [];
  const notificationItems = useMemo(() => {
    return (notificationFeedQuery.data ?? [])
      .slice()
      .sort((first, second) => {
        const firstTime = Date.parse(first.created_at);
        const secondTime = Date.parse(second.created_at);
        if (Number.isNaN(firstTime) || Number.isNaN(secondTime)) {
          return second.id - first.id;
        }
        return secondTime - firstTime;
      })
      .slice(0, 8);
  }, [notificationFeedQuery.data]);
  const unreadNotificationCount = nudgeOpenCountQuery.data?.total ?? notificationFeedQuery.data?.length ?? 0;
  const notificationAriaLabel =
    unreadNotificationCount > 0
      ? `Notifications (${toCompactNumber(unreadNotificationCount)} open)`
      : "Notifications";
  const notificationBadgeLabel = unreadNotificationCount > 0 ? toCompactNumber(unreadNotificationCount) : "0";

  const loadingInitial = data.orgHealth.isLoading || risksQuery.isLoading || nudgesQuery.isLoading;
  const hasWorkforceData = !canReadInsights || (data.orgHealth.data?.active_headcount ?? 0) > 0;

  const hasApiError = [
    data.orgHealth.error,
    risksQuery.error,
    nudgesQuery.error,
    headcountQuery.error,
    riskTrendsQuery.error,
    cohortsQuery.error,
    anomaliesQuery.error,
    ingestionRunsQuery.error,
    employeesQuery.error,
    onaQuery.error,
    notificationFeedQuery.error,
    nudgeOpenCountQuery.error,
    planningFinance.error,
    workforceFinance.error,
    employeeProfile.error,
    employeeTimeline.error,
    managerTeam.error,
    nudgeFeedback.error,
    authContext.error,
    authUsersQuery.error,
  ].find(Boolean);

  useEffect(() => {
    if (!hasApiError) {
      return;
    }
    pushToast("error", errorMessage(hasApiError));
  }, [hasApiError, pushToast]);

  useEffect(() => {
    if (!loadingInitial && !hasApiError && !hasWorkforceData) {
      pushToast("error", "No live workforce records found. Send dynamic data via /api/v1/ingest/workforce.");
    }
  }, [loadingInitial, hasApiError, hasWorkforceData, pushToast]);

  const tabs = TAB_CONFIG;
  const showOverviewKpis = tab === "overview" && canReadInsights && !loadingInitial && !hasApiError && hasWorkforceData;

  const currentPermissions = useMemo(
    () => new Set(authContext.data?.permissions ?? Array.from(rolePermissions)),
    [authContext.data?.permissions, rolePermissions],
  );
  const canAccess = (permission: string): boolean => currentPermissions.has(permission);
  const canManageEmployeeProfiles = canAccess("employees.write");

  const availableTabs = useMemo(
    () =>
      tabs.filter((item) =>
        item.requiredPermissions.every(
          (permission) => currentPermissions.has(permission),
        ),
      ),
    [currentPermissions, tabs],
  );

  useEffect(() => {
    if (!isViewTab(tabParam)) {
      navigate("/dashboard/overview", { replace: true });
    }
  }, [tabParam, navigate]);

  useEffect(() => {
    if (!availableTabs.length) {
      return;
    }
    if (!availableTabs.some((item) => item.key === tab)) {
      navigate(`/dashboard/${availableTabs[0].key}`, { replace: true });
    }
  }, [availableTabs, tab, navigate]);

  const roleOptions = authContext.data?.available_roles ?? FALLBACK_ROLES;
  const profileName = authContext.data?.user?.full_name ?? "Workforce User";
  const profileEmail = authContext.data?.user?.email || loginEmail || "secured@dattamsha.local";
  const profileInitials = profileName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "DD";
  useEffect(() => {
    if (!canReadNudges && showNotifications) {
      setShowNotifications(false);
    }
  }, [canReadNudges, showNotifications]);
  useEffect(() => {
    if (tab === "alerts") {
      setShowNotifications(false);
    }
  }, [tab]);
  const filteredRolePermissions = useMemo(() => {
    const matrix =
      authContext.data?.role_permissions ??
      Object.entries(ROLE_PERMISSION_MATRIX).map(([role, permissions]) => ({
        role,
        permissions,
      }));
    return matrix
      .map((entry) => ({
        role: entry.role,
        permissions: entry.permissions.filter((permission) =>
          matchesSearch(rbacPermissionSearch, permission, entry.role),
        ),
      }))
      .filter((entry) => entry.permissions.length > 0 || matchesSearch(rbacPermissionSearch, entry.role));
  }, [authContext.data?.role_permissions, rbacPermissionSearch]);
  const closeEmployeeProfileModal = (): void => {
    if (createEmployeeMutation.isPending || updateEmployeeMutation.isPending) {
      return;
    }
    setEmployeeProfileModalOpen(false);
  };
  const openCreateEmployeeProfileModal = (): void => {
    setEmployeeProfileModalMode("create");
    setEmployeeProfileForm({ ...DEFAULT_EMPLOYEE_PROFILE_FORM });
    setEmployeeProfileModalOpen(true);
  };
  const openEditEmployeeProfileModal = (): void => {
    if (!employeeProfile.data) {
      pushToast("error", "Load an employee profile before editing.");
      return;
    }
    setEmployeeProfileModalMode("edit");
    setEmployeeProfileForm(mapProfileToForm(employeeProfile.data));
    setEmployeeProfileModalOpen(true);
  };
  const handleEmployeeAvatarUpload = (file: File): void => {
    const maxBytes = 350 * 1024;
    if (file.size > maxBytes) {
      pushToast("error", "Image too large. Max size is 350KB.");
      return;
    }
    if (!file.type.startsWith("image/")) {
      pushToast("error", "Please upload a valid image file.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      if (!result.startsWith("data:image/")) {
        pushToast("error", "Image encoding failed. Please try another file.");
        return;
      }
      setEmployeeProfileForm((previous) => ({ ...previous, avatar_image_base64: result }));
    };
    reader.onerror = () => {
      pushToast("error", "Unable to read image file.");
    };
    reader.readAsDataURL(file);
  };
  const submitEmployeeProfileForm = (): void => {
    const payload = buildEmployeePayloadFromForm(employeeProfileForm);
    if (!payload.external_id || !payload.full_name || !payload.email || !payload.department || !payload.role) {
      pushToast("error", "Please complete all required employee fields.");
      return;
    }
    if (employeeProfileModalMode === "create") {
      createEmployeeMutation.mutate(payload);
      return;
    }
    if (!employeeProfile.data) {
      pushToast("error", "Employee profile is not loaded.");
      return;
    }
    updateEmployeeMutation.mutate({
      id: employeeProfile.data.employee.id,
      payload: payload as EmployeeUpdateRequest,
    });
  };
  const toastStack = toasts.length ? (
    <div className="toast-area" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <StatusBanner
          key={toast.id}
          type={toast.type}
          message={toast.message}
          onClose={() => dismissToast(toast.id)}
        />
      ))}
    </div>
  ) : null;

  if (authConfig.isLoading) {
    return (
      <div className="app-shell">
        <p className="loading-hint">Checking authentication settings...</p>
        {toastStack}
      </div>
    );
  }

  if (isAuthRequired && !isLoggedIn) {
    return (
      <div className="app-shell auth-shell">
        <motion.section
          className="auth-hero"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
        >
          <div className="auth-hero-top">
            <span className="sidebar-logo">DD</span>
            <p>Dattamsha Workforce Intelligence</p>
          </div>
          <h2>Operate HR with Real-Time Intelligence</h2>
          <p>
            Unify employee data, detect risks early, and trigger manager actions from one secure platform.
          </p>
          <div className="auth-hero-panel">
            <div className="auth-hero-stat">
              <strong>{toCompactNumber(data.orgHealth.data?.active_headcount ?? 0)}</strong>
              <span>Employees monitored</span>
            </div>
            <div className="auth-hero-stat">
              <strong>{String(data.orgHealth.data?.high_attrition_risk_count ?? 0)}</strong>
              <span>Open attrition alerts</span>
            </div>
            <div className="auth-hero-stat">
              <strong>{String(filteredNudges.length)}</strong>
              <span>Behavior nudges generated</span>
            </div>
          </div>
        </motion.section>

        <motion.section
          className="panel auth-panel auth-panel-enterprise"
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.35, ease: "easeOut", delay: 0.08 }}
        >
          <div className="auth-panel-header">
            <p className="brand-eyebrow">Secure Login</p>
            <h2>Get started with your email</h2>
            <p>Account provisioning is controlled by platform admins only.</p>
          </div>
          <form
            className="auth-form-stack"
            onSubmit={(event) => {
              event.preventDefault();
              if (!loginEmail.trim() || !loginPassword.trim()) {
                pushToast("error", "Email and password are required.");
                return;
              }
              loginMutation.mutate();
            }}
          >
            <label className="input-stack">
              Email
              <input
                type="email"
                value={loginEmail}
                onChange={(event) => setLoginEmail(event.target.value)}
                placeholder="admin@dattamsha.local"
                autoComplete="username"
              />
            </label>
            <label className="input-stack">
              Password
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
              />
            </label>
            <button className="btn auth-submit" type="submit" disabled={loginMutation.isPending}>
              {loginMutation.isPending ? "Signing in..." : "Continue"}
            </button>
          </form>
          <div className="auth-links">
            <NavLink to="/terms-and-conditions">Terms & Conditions</NavLink>
            <span>|</span>
            <NavLink to="/privacy-policy">Privacy Policy</NavLink>
          </div>
        </motion.section>
        {toastStack}
      </div>
    );
  }

  if (isAuthRequired && isLoggedIn && authContext.isLoading) {
    return (
      <div className="app-shell">
        <p className="loading-hint">Validating your session...</p>
        {toastStack}
      </div>
    );
  }

  return (
    <div className={`app-shell ${showFilters ? "filters-visible" : "filters-hidden"}`}>
      <aside className="workspace-sidebar app-sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo">DD</span>
          <div className="sidebar-brand-copy">
            <p className="sidebar-brand-title">Dattamsha</p>
            <small>Workforce Intelligence</small>
          </div>
        </div>
        <nav className="main-tabs app-nav" aria-label="Dashboard sections">
          {availableTabs.map((item) => {
            const Icon = item.icon;
            return (
                <button
                  key={item.key}
                  className={`tab-btn ${tab === item.key ? "active" : ""}`}
                  onClick={() => goToTab(item.key)}
                >
                <span className="tab-btn-icon">
                  <Icon size={16} />
                </span>
                <span className="tab-btn-copy">
                  <span className="tab-btn-label">{item.label}</span>
                  <span className="tab-btn-hint">{item.description}</span>
                </span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-card sidebar-signal-card">
          <p className="sidebar-label">Live Signals</p>
          <div className="sidebar-stat-row">
            <span>Open Nudges</span>
            <strong>{filteredNudges.length}</strong>
          </div>
          <div className="sidebar-stat-row">
            <span>Risk Records</span>
            <strong>{filteredRisks.length}</strong>
          </div>
          <div className="sidebar-stat-row">
            <span>Headcount</span>
            <strong>{toCompactNumber(data.orgHealth.data?.active_headcount ?? 0)}</strong>
          </div>
        </div>
        <div className="sidebar-footer">
          {isAuthRequired ? (
            <button
              className="tab-btn tab-btn-flat"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
            >
              <span className="tab-btn-icon">
                <LogOut size={16} />
              </span>
              <span className="tab-btn-copy">
                <span className="tab-btn-label">
                  {logoutMutation.isPending ? "Signing out..." : "Log Out"}
                </span>
                <span className="tab-btn-hint">End secure session</span>
              </span>
            </button>
          ) : null}
        </div>
      </aside>

      <motion.div
        className="app-main"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
      >
        <header className="topbar app-topbar">
          <div className="topbar-row topbar-row-controls">
            <div className="topbar-actions">
            {!isAuthRequired ? (
              <label className="role-switch">
                Active Role
                <select
                  value={userRole}
                  onChange={(event) => setUserRole(event.target.value as UserRole)}
                >
                  {roleOptions.map((role) => (
                    <option key={role} value={role}>
                      {role.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button className="btn secondary" onClick={() => setShowFilters((previous) => !previous)}>
              {showFilters ? "Hide Filters" : "Show Filters"}
            </button>
            <button className="btn secondary" onClick={() => setShowAdvanced((previous) => !previous)}>
              {showAdvanced ? "Basic View" : "Advanced View"}
            </button>
            <div className="profile-chip">
              <span className="profile-avatar">{profileInitials}</span>
              <span className="profile-copy">
                <strong>{profileName}</strong>
                <small>{profileEmail}</small>
              </span>
              {canReadNudges ? (
                <div className="notification-wrap" ref={notificationMenuRef}>
                  <button
                    className={`icon-btn notification-trigger ${showNotifications ? "active" : ""}`}
                    type="button"
                    aria-label={notificationAriaLabel}
                    aria-expanded={showNotifications}
                    aria-haspopup="menu"
                    onClick={() => {
                      setShowNotifications((previous) => !previous);
                    }}
                  >
                    <Bell size={16} />
                    {unreadNotificationCount > 0 ? (
                      <span className="notification-badge">{notificationBadgeLabel}</span>
                    ) : null}
                  </button>
                  {showNotifications ? (
                    <section className="notification-panel" role="menu" aria-label="Open notifications">
                      <header className="notification-header">
                        <div>
                          <p>Notifications</p>
                          <small>{toCompactNumber(unreadNotificationCount)} open nudges</small>
                        </div>
                        <button
                          className="btn secondary btn-sm"
                          type="button"
                          onClick={() => {
                            void notificationFeedQuery.refetch();
                            void nudgeOpenCountQuery.refetch();
                          }}
                          disabled={notificationFeedQuery.isFetching || nudgeOpenCountQuery.isFetching}
                        >
                          {notificationFeedQuery.isFetching || nudgeOpenCountQuery.isFetching
                            ? "Refreshing..."
                            : "Refresh"}
                        </button>
                      </header>
                      <div className="notification-list">
                        {notificationFeedQuery.isLoading ? (
                          <p className="notification-empty">Loading notifications...</p>
                        ) : null}
                        {!notificationFeedQuery.isLoading && !notificationItems.length ? (
                          <p className="notification-empty">No open alerts right now.</p>
                        ) : null}
                        {!notificationFeedQuery.isLoading
                          ? notificationItems.map((item) => (
                              <button
                                key={item.id}
                                className="notification-item"
                                type="button"
                                onClick={() => {
                                  setShowNotifications(false);
                                  goToTab("alerts");
                                }}
                              >
                                <span className={`notification-severity ${item.severity.toLowerCase()}`}>
                                  {item.severity}
                                </span>
                                <strong>{item.nudge_type.replaceAll("_", " ")}</strong>
                                <p>{item.message}</p>
                                <small>{toDate(item.created_at)}</small>
                              </button>
                            ))
                          : null}
                      </div>
                    </section>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
          </div>
        </header>
        {toastStack}

        {showAdvanced || tab === "settings" ? (
          <section className="setup-card">
            <div className="setup-grid">
              <label className="input-stack">
                API Key (if enabled)
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Paste key only if backend requires it"
                />
              </label>

              <label className="input-stack narrow">
                Employee ID
                <input
                  type="number"
                  min={1}
                  value={employeeId}
                  onChange={(event) => setEmployeeId(Number(event.target.value))}
                />
              </label>

              <label className="input-stack narrow">
                Manager ID
                <input
                  type="number"
                  min={1}
                  value={managerId}
                  onChange={(event) => setManagerId(Number(event.target.value))}
                />
              </label>

              <label className="input-stack narrow">
                Annual Revenue
                <input
                  type="number"
                  min={0}
                  value={annualRevenue}
                  onChange={(event) => setAnnualRevenue(Number(event.target.value))}
                />
              </label>

              <div className="action-row">
                <button
                  className="btn secondary"
                  onClick={() => {
                    pushToast("ok", "Data refresh complete.");
                    void queryClient.invalidateQueries();
                  }}
                >
                  <RefreshCcw size={16} /> Refresh Data
                </button>
              </div>
            </div>
          </section>
        ) : null}

      {loadingInitial ? <p className="loading-hint">Loading latest workforce data...</p> : null}

      {showOverviewKpis ? (
        <section className="metrics-row">
          <MetricCard
            label="Active Employees"
            value={toCompactNumber(data.orgHealth.data?.active_headcount ?? 0)}
            hint="Current active workforce"
          />
          <MetricCard
            label="Avg Engagement"
            value={toPercent(data.orgHealth.data?.average_engagement)}
            hint="Pulse + sentiment signals"
            tone="good"
          />
          <MetricCard
            label="Attrition Alerts"
            value={String(data.orgHealth.data?.high_attrition_risk_count ?? 0)}
            hint="Needs manager action"
            tone="warn"
          />
          <MetricCard
            label="People Risk Cost"
            value={workforceFinance.data ? toCurrency(workforceFinance.data.total_people_risk_cost) : "-"}
            hint="Attrition + burnout estimated cost"
            tone="warn"
          />
        </section>
      ) : null}

      {tab === "overview" && !canReadInsights ? (
        <div className="empty-state">Current role has restricted analytics access. Open Settings to switch role.</div>
      ) : null}

      <div className="workspace-layout">
        <div className="workspace-main">
      {tab === "overview" ? (
        <main className="section-grid split-grid">
          <Panel title="Department Distribution" subtitle="Headcount by department">
            <div className="filter-row">
              <label className="input-stack">
                Search Department
                <input
                  value={departmentSearch}
                  onChange={(event) => setDepartmentSearch(event.target.value)}
                  placeholder="Type department"
                />
              </label>
              <label className="input-stack">
                Department Filter
                <select
                  value={overviewDepartmentFilter}
                  onChange={(event) => setOverviewDepartmentFilter(event.target.value)}
                >
                  <option value="all">All departments</option>
                  {departmentOptions.map((department) => (
                    <option key={department} value={department}>
                      {department}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={headcountChartData}
                    dataKey="count"
                    nameKey="department"
                    cx="50%"
                    cy="50%"
                    outerRadius={95}
                  >
                    {headcountChartData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Top Risk Employees" subtitle="Attrition vs burnout (top 8)">
            <div className="filter-row">
              <label className="input-stack">
                Search Employee
                <input
                  value={overviewEmployeeSearch}
                  onChange={(event) => setOverviewEmployeeSearch(event.target.value)}
                  placeholder="Name, id, department"
                />
              </label>
              <label className="input-stack">
                Department
                <select
                  value={overviewDepartmentFilter}
                  onChange={(event) => setOverviewDepartmentFilter(event.target.value)}
                >
                  <option value="all">All departments</option>
                  {departmentOptions.map((department) => (
                    <option key={department} value={department}>
                      {department}
                    </option>
                  ))}
                </select>
              </label>
              <label className="input-stack">
                Minimum Risk
                <select
                  value={overviewMinRiskFilter}
                  onChange={(event) => setOverviewMinRiskFilter(event.target.value)}
                >
                  <option value="0">All</option>
                  <option value="0.4">40%+</option>
                  <option value="0.6">60%+</option>
                  <option value="0.8">80%+</option>
                </select>
              </label>
            </div>
            <p className="filter-note">Showing {filteredRisks.length} matching employees.</p>
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={riskChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e8f1" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} height={56} textAnchor="end" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="attrition" fill="#3f7af6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="burnout" fill="#f2994a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {showAdvanced ? (
            <Panel title="Risk Trends" subtitle="Recent trend of engagement, attrition and burnout">
            <div className="filter-row">
              <label className="input-stack">
                Search Date
                <input
                  value={trendSearch}
                  onChange={(event) => setTrendSearch(event.target.value)}
                  placeholder="YYYY-MM-DD"
                />
              </label>
              <label className="input-stack">
                Metric Focus
                <select
                  value={trendMetricFilter}
                  onChange={(event) => setTrendMetricFilter(event.target.value)}
                >
                  <option value="all">All metrics</option>
                  <option value="engagement">Engagement only</option>
                  <option value="attrition">Attrition only</option>
                  <option value="burnout">Burnout only</option>
                </select>
              </label>
            </div>
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={trendChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e8f1" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={4} />
                  <YAxis />
                  <Tooltip />
                  {(trendMetricFilter === "all" || trendMetricFilter === "engagement") ? (
                    <Bar dataKey="engagement" fill="#2bb673" radius={[4, 4, 0, 0]} />
                  ) : null}
                  {(trendMetricFilter === "all" || trendMetricFilter === "attrition") ? (
                    <Bar dataKey="attrition" fill="#3f7af6" radius={[4, 4, 0, 0]} />
                  ) : null}
                  {(trendMetricFilter === "all" || trendMetricFilter === "burnout") ? (
                    <Bar dataKey="burnout" fill="#f2994a" radius={[4, 4, 0, 0]} />
                  ) : null}
                </BarChart>
              </ResponsiveContainer>
            </div>
            </Panel>
          ) : null}

          {showAdvanced ? (
            <Panel title="Cohort Risk View" subtitle="Department segmentation with high-risk counts">
            <div className="filter-row">
              <label className="input-stack">
                Search Cohort
                <input
                  value={cohortSearch}
                  onChange={(event) => setCohortSearch(event.target.value)}
                  placeholder="Department"
                />
              </label>
            </div>
            {filteredCohorts.length === 0 ? (
              <div className="empty-state">No cohort analytics available yet.</div>
            ) : (
              <div className="simple-list">
                {filteredCohorts.slice(0, 8).map((cohort) => (
                  <div key={cohort.cohort} className="simple-card">
                    <h3>{cohort.cohort}</h3>
                    <p>
                      Headcount {cohort.headcount} • Attrition {toPercent(cohort.avg_attrition_risk)} • Burnout {toPercent(cohort.avg_burnout_risk)}
                    </p>
                    <small>
                      High attrition: {cohort.high_attrition_count} • High burnout: {cohort.high_burnout_count}
                    </small>
                  </div>
                ))}
              </div>
            )}
            </Panel>
          ) : null}

          {showAdvanced ? (
            <Panel title="Risk Anomalies" subtitle="Departments with abnormal risk spikes">
            <div className="filter-row">
              <label className="input-stack">
                Search Anomaly
                <input
                  value={anomalySearch}
                  onChange={(event) => setAnomalySearch(event.target.value)}
                  placeholder="Cohort or metric"
                />
              </label>
              <label className="input-stack">
                Severity
                <select
                  value={anomalySeverityFilter}
                  onChange={(event) => setAnomalySeverityFilter(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </div>
            {filteredAnomalies.length === 0 ? (
              <div className="empty-state">No significant anomalies detected at current thresholds.</div>
            ) : (
              <div className="simple-list">
                {filteredAnomalies.map((anomaly, index) => (
                  <div key={`${anomaly.cohort}-${anomaly.metric}-${index}`} className={`nudge-item severity-${anomaly.severity}`}>
                    <div>
                      <p className="nudge-title">{anomaly.cohort} • {anomaly.metric.replaceAll("_", " ")}</p>
                      <p>
                        Value {toPercent(anomaly.value)} vs baseline {toPercent(anomaly.baseline)} (delta {toPercent(anomaly.delta)})
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            </Panel>
          ) : null}

          <Panel title="Workforce Finance" subtitle="Payroll and risk cost linkage">
            <div className="filter-row">
              <label className="input-stack">
                Search Department
                <input
                  value={financeSearch}
                  onChange={(event) => setFinanceSearch(event.target.value)}
                  placeholder="Department name"
                />
              </label>
            </div>
            <div className="result-grid">
              <MetricCard
                label="Annual Payroll"
                value={workforceFinance.data ? toCurrency(workforceFinance.data.annual_payroll) : "-"}
              />
              <MetricCard
                label="Attrition Cost"
                value={workforceFinance.data ? toCurrency(workforceFinance.data.estimated_attrition_cost) : "-"}
                tone="warn"
              />
              <MetricCard
                label="Burnout Cost"
                value={workforceFinance.data ? toCurrency(workforceFinance.data.estimated_burnout_cost) : "-"}
                tone="warn"
              />
              <MetricCard
                label="Salary/Revenue"
                value={workforceFinance.data?.salary_to_revenue_ratio != null ? `${(workforceFinance.data.salary_to_revenue_ratio * 100).toFixed(2)}%` : "-"}
              />
            </div>
            <div className="simple-list">
              {filteredFinanceDepartments.slice(0, 6).map((dept) => (
                <div key={dept.department} className="simple-card">
                  <h3>{dept.department}</h3>
                  <p>
                    Payroll {toCurrency(dept.annual_payroll)} • Headcount {dept.headcount}
                  </p>
                </div>
              ))}
            </div>
          </Panel>

          {showAdvanced && canAccess("ingest.read") ? (
            <Panel title="Ingestion Runs" subtitle="Latest dynamic data pipeline executions">
            <div className="filter-row">
              <label className="input-stack">
                Search Runs
                <input
                  value={ingestionSearch}
                  onChange={(event) => setIngestionSearch(event.target.value)}
                  placeholder="Run id, source, status"
                />
              </label>
              <label className="input-stack">
                Status
                <select
                  value={ingestionStatusFilter}
                  onChange={(event) => setIngestionStatusFilter(event.target.value)}
                >
                  <option value="all">All statuses</option>
                  <option value="success">Success</option>
                  <option value="failed">Failed</option>
                </select>
              </label>
            </div>
            {filteredIngestionRuns.length === 0 ? (
              <div className="empty-state">No ingestion runs found yet. Use /api/v1/ingest/workforce to load data.</div>
            ) : (
              <div className="simple-list">
                {filteredIngestionRuns.map((run) => (
                  <div key={run.id} className="simple-card">
                    <h3>Run #{run.id} • {run.source}</h3>
                    <p>
                      Status {run.status} • Records {run.records_received} • Employees {run.employees_upserted} • Metrics {run.metrics_upserted}
                    </p>
                    <small>{toDate(run.created_at)}</small>
                  </div>
                ))}
              </div>
            )}
            </Panel>
          ) : null}

          {showAdvanced && canAccess("ingest.write") ? (
            <Panel
            title="Ingestion Console"
            subtitle="Post dynamic workforce payload directly from UI"
            actions={
              <button
                className="btn"
                onClick={() => ingestMutation.mutate()}
                disabled={ingestMutation.isPending}
              >
                {ingestMutation.isPending ? "Ingesting..." : "Run Ingestion"}
              </button>
            }
          >
            <label className="input-stack">
              JSON Payload (`/api/v1/ingest/workforce`)
              <textarea
                rows={9}
                value={ingestPayloadText}
                onChange={(event) => setIngestPayloadText(event.target.value)}
              />
            </label>
            </Panel>
          ) : null}

          {showAdvanced ? (
            <Panel title="Network Health" subtitle="Collaboration graph indicators">
            {onaQuery.data ? (
              <div className="ona-cards">
                <label className="input-stack span-2">
                  Search Employee ID
                  <input
                    value={networkSearch}
                    onChange={(event) => setNetworkSearch(event.target.value)}
                    placeholder="Filter node ids"
                  />
                </label>
                <MetricCard label="Average Degree" value={onaQuery.data.average_degree.toFixed(2)} />
                <div className="simple-card">
                  <h3>Most Connected IDs</h3>
                  <p>{filteredCentralIds.join(", ") || "-"}</p>
                </div>
                <div className="simple-card">
                  <h3>Most Isolated IDs</h3>
                  <p>{filteredIsolatedIds.join(", ") || "-"}</p>
                </div>
              </div>
            ) : (
              <div className="empty-state">ONA data is not available yet.</div>
            )}
            </Panel>
          ) : null}
        </main>
      ) : null}

      {tab === "alerts" ? (
        <main className="section-grid">
          <Panel
            title="Manager Team Overview"
            subtitle="Team health and recommended interventions"
            actions={
              <button className="btn secondary" onClick={() => managerTeam.refetch()}>
                <Search size={16} /> Load Manager Team
              </button>
            }
          >
            {managerTeam.data ? (
              <>
                <div className="filter-row">
                  <label className="input-stack">
                    Search Team Member
                    <input
                      value={teamSearch}
                      onChange={(event) => setTeamSearch(event.target.value)}
                      placeholder="Name, role, department"
                    />
                  </label>
                  <label className="input-stack">
                    Risk Band
                    <select
                      value={teamRiskFilter}
                      onChange={(event) => setTeamRiskFilter(event.target.value)}
                    >
                      <option value="all">All</option>
                      <option value="high">High (70%+)</option>
                      <option value="medium">Medium (50-69%)</option>
                      <option value="low">Low (&lt;50%)</option>
                    </select>
                  </label>
                </div>
                <div className="result-grid">
                  <MetricCard label="Team Size" value={String(managerTeam.data.team_size)} />
                  <MetricCard label="Avg Attrition" value={toPercent(managerTeam.data.average_attrition_risk)} tone="warn" />
                  <MetricCard label="Avg Burnout" value={toPercent(managerTeam.data.average_burnout_risk)} tone="warn" />
                  <MetricCard label="Open Nudges" value={String(managerTeam.data.open_nudges)} />
                </div>
                <div className="simple-list">
                  {managerTeam.data.recommended_actions.map((action, index) => (
                    <div key={index} className="simple-card">
                      <p>{action}</p>
                    </div>
                  ))}
                </div>
                {(filteredTeamMembers.length === 0) ? (
                  <div className="empty-state">No team members match current filters.</div>
                ) : (
                  <div className="simple-list">
                    {filteredTeamMembers.map((member) => (
                      <div key={member.employee_id} className="simple-card">
                        <h3>#{member.employee_id} {member.full_name}</h3>
                        <p>
                          {member.role} • {member.department}
                        </p>
                        <small>
                          Attrition {toPercent(member.attrition_risk)} • Burnout {toPercent(member.burnout_risk)} • Open nudges {member.open_nudges}
                        </small>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">Enter manager id and load team overview.</div>
            )}
          </Panel>

          <Panel
            title="Manager Action Queue"
            subtitle="Nudges requiring immediate attention"
            actions={
              canAccess("nudges.write") ? (
                <div className="action-row">
                  <button
                    className="btn"
                    onClick={() => generateNudgeMutation.mutate()}
                    disabled={generateNudgeMutation.isPending}
                  >
                    <Sparkles size={16} />
                    {generateNudgeMutation.isPending ? "Generating..." : "Generate Nudges"}
                  </button>
                  <button
                    className="btn secondary"
                    onClick={() => dispatchMutation.mutate(dispatchInput)}
                    disabled={dispatchMutation.isPending}
                  >
                    <Send size={16} />
                    {dispatchMutation.isPending ? "Dispatching..." : "Dispatch Nudges"}
                  </button>
                </div>
              ) : (
                <small>Read-only mode for current role.</small>
              )
            }
          >
            <div className="filter-row">
              <label className="input-stack">
                Search Nudges
                <input
                  value={nudgeSearch}
                  onChange={(event) => setNudgeSearch(event.target.value)}
                  placeholder="Type, message, employee"
                />
              </label>
              <label className="input-stack">
                Severity
                <select
                  value={nudgeSeverityFilter}
                  onChange={(event) => setNudgeSeverityFilter(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </div>
            {canAccess("nudges.write") ? (
              <div className="form-grid">
                <label className="input-stack">
                  Dispatch Channel
                  <select
                    value={dispatchInput.channel}
                    onChange={(event) =>
                      setDispatchInput((prev) => ({
                        ...prev,
                        channel: event.target.value as "console" | "webhook",
                      }))
                    }
                  >
                    <option value="console">Console</option>
                    <option value="webhook">Webhook</option>
                  </select>
                </label>
                <label className="input-stack">
                  Webhook URL (if webhook)
                  <input
                    value={dispatchInput.webhook_url ?? ""}
                    onChange={(event) => setDispatchInput((prev) => ({ ...prev, webhook_url: event.target.value }))}
                    placeholder="https://hooks.slack.com/..."
                  />
                </label>
              </div>
            ) : null}

            {filteredNudges.length === 0 ? (
              <div className="empty-state">No open nudges. Team looks healthy right now.</div>
            ) : (
              <div className="simple-list">
                {filteredNudges.map((nudge) => (
                  <article key={nudge.id} className={`nudge-item severity-${nudge.severity}`}>
                    <div>
                      <p className="nudge-title">#{nudge.id} • {nudge.nudge_type.replaceAll("_", " ")}</p>
                      <p>{nudge.message}</p>
                      <small>{nudge.evidence}</small>
                      <small>Created: {toDate(nudge.created_at)}</small>
                    </div>
                    {canAccess("nudges.write") ? (
                      <button
                        className="btn secondary"
                        onClick={() => resolveNudgeMutation.mutate(nudge.id)}
                        disabled={resolveNudgeMutation.isPending}
                      >
                        Resolve
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </Panel>

          {showAdvanced && canAccess("nudges.write") ? (
            <Panel title="Intervention Feedback" subtitle="Capture manager action quality for nudges">
            {selectedNudgeId > 0 ? (
              <form
                className="form-grid"
                onSubmit={(event) => {
                  event.preventDefault();
                  createFeedbackMutation.mutate(feedbackInput);
                }}
              >
                <label className="input-stack">
                  Target Nudge ID
                  <input type="number" value={selectedNudgeId} readOnly />
                </label>
                <label className="input-stack">
                  Manager Identifier
                  <input
                    value={feedbackInput.manager_identifier}
                    onChange={(event) =>
                      setFeedbackInput((prev) => ({ ...prev, manager_identifier: event.target.value }))
                    }
                  />
                </label>
                <label className="input-stack span-2">
                  Action Taken
                  <textarea
                    rows={3}
                    value={feedbackInput.action_taken}
                    onChange={(event) =>
                      setFeedbackInput((prev) => ({ ...prev, action_taken: event.target.value }))
                    }
                  />
                </label>
                <label className="input-stack">
                  Effectiveness (1-5)
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={feedbackInput.effectiveness_rating}
                    onChange={(event) =>
                      setFeedbackInput((prev) => ({ ...prev, effectiveness_rating: Number(event.target.value) }))
                    }
                  />
                </label>
                <label className="input-stack">
                  Notes
                  <input
                    value={feedbackInput.notes ?? ""}
                    onChange={(event) => setFeedbackInput((prev) => ({ ...prev, notes: event.target.value }))}
                  />
                </label>
                <button className="btn" type="submit" disabled={createFeedbackMutation.isPending}>
                  {createFeedbackMutation.isPending ? "Saving..." : "Submit Feedback"}
                </button>
              </form>
            ) : (
              <div className="empty-state">Generate nudges first to capture feedback.</div>
            )}

            <div className="filter-row">
              <label className="input-stack">
                Search Feedback
                <input
                  value={feedbackSearch}
                  onChange={(event) => setFeedbackSearch(event.target.value)}
                  placeholder="Manager, action, notes"
                />
              </label>
              <label className="input-stack">
                Rating
                <select
                  value={feedbackRatingFilter}
                  onChange={(event) => setFeedbackRatingFilter(event.target.value)}
                >
                  <option value="all">All ratings</option>
                  <option value="5">5</option>
                  <option value="4">4</option>
                  <option value="3">3</option>
                  <option value="2">2</option>
                  <option value="1">1</option>
                </select>
              </label>
            </div>

            {filteredFeedback.length > 0 ? (
              <div className="simple-list">
                {filteredFeedback.slice(0, 8).map((feedback) => (
                  <div key={feedback.id} className="simple-card">
                    <h3>{feedback.manager_identifier} • Rating {feedback.effectiveness_rating}/5</h3>
                    <p>{feedback.action_taken}</p>
                    {feedback.notes ? <small>{feedback.notes}</small> : null}
                  </div>
                ))}
              </div>
            ) : null}
            </Panel>
          ) : null}
        </main>
      ) : null}

      {tab === "employee" ? (
        <main className="section-grid">
          <Panel
            title="Employee Details"
            subtitle="Single employee health view"
            actions={
              <div className="action-row">
                <button className="btn secondary" onClick={() => employeeProfile.refetch()}>
                  <Search size={16} /> Load Employee
                </button>
                {canManageEmployeeProfiles ? (
                  <>
                    <button className="btn" onClick={openCreateEmployeeProfileModal}>
                      Add Profile
                    </button>
                    <button
                      className="btn secondary"
                      onClick={openEditEmployeeProfileModal}
                      disabled={!employeeProfile.data}
                    >
                      Edit Profile
                    </button>
                    <button
                      className="btn danger"
                      onClick={() => setEmployeeDeleteModalOpen(true)}
                      disabled={!employeeProfile.data || deleteEmployeeMutation.isPending}
                    >
                      {deleteEmployeeMutation.isPending ? "Deleting..." : "Delete Profile"}
                    </button>
                  </>
                ) : null}
              </div>
            }
          >
            <div className="form-grid">
              <label className="input-stack span-2">
                Search Employee
                <input
                  value={employeeSearch}
                  onChange={(event) => setEmployeeSearch(event.target.value)}
                  placeholder="Name, id, role, department"
                />
              </label>
              <label className="input-stack span-2">
                Quick Employee Select
                <select
                  value={employeeId}
                  onChange={(event) => setEmployeeId(Number(event.target.value))}
                >
                  {filteredEmployeeOptions.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      #{employee.id} {employee.full_name} • {employee.department}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {employeeProfile.data ? (
              <div className="employee-card">
                <div className="employee-meta">
                  <div className="employee-profile-top">
                    {employeeProfile.data.profile_details?.avatar_image_base64 ? (
                      <img
                        className="employee-avatar-preview"
                        src={employeeProfile.data.profile_details.avatar_image_base64}
                        alt={`${employeeProfile.data.employee.full_name} avatar`}
                      />
                    ) : (
                      <span className="employee-avatar-fallback">
                        {employeeProfile.data.employee.full_name
                          .split(" ")
                          .filter(Boolean)
                          .slice(0, 2)
                          .map((part) => part[0]?.toUpperCase() ?? "")
                          .join("") || "EMP"}
                      </span>
                    )}
                    <div>
                      <h3>{employeeProfile.data.employee.full_name}</h3>
                      <p>
                        {employeeProfile.data.employee.role} • {employeeProfile.data.employee.department}
                      </p>
                      <p>{employeeProfile.data.employee.location}</p>
                      <small>
                        Hired: {employeeProfile.data.employee.hire_date} • Status: {employeeProfile.data.employee.employment_status}
                      </small>
                    </div>
                  </div>
                  <div className="employee-meta-extra">
                    <small>Email: {employeeProfile.data.employee.email}</small>
                    <small>Employee ID: {employeeProfile.data.employee.external_id}</small>
                    <small>Preferred Name: {employeeProfile.data.profile_details?.preferred_name ?? "-"}</small>
                    <small>Phone: {employeeProfile.data.profile_details?.phone ?? "-"}</small>
                    <small>
                      Emergency Contact:{" "}
                      {employeeProfile.data.profile_details?.emergency_contact_name
                        ? `${employeeProfile.data.profile_details.emergency_contact_name} (${employeeProfile.data.profile_details.emergency_contact_phone ?? "-"})`
                        : "-"}
                    </small>
                    <small>Address: {employeeProfile.data.profile_details?.address ?? "-"}</small>
                    <small>Skills: {employeeProfile.data.profile_details?.skills ?? "-"}</small>
                  </div>
                </div>

                <div className="risk-pills">
                  <MetricCard label="Attrition" value={toPercent(employeeProfile.data.attrition_risk)} tone="warn" />
                  <MetricCard label="Burnout" value={toPercent(employeeProfile.data.burnout_risk)} tone="warn" />
                  <MetricCard label="Engagement" value={toPercent(employeeProfile.data.engagement_score)} tone="good" />
                  <MetricCard label="Goal Completion" value={toPercent(employeeProfile.data.goal_completion_pct)} />
                </div>
              </div>
            ) : (
              <div className="empty-state">Set an Employee ID and click Load Employee.</div>
            )}

            {showAdvanced ? (
              <>
                <div className="filter-row">
                  <label className="input-stack">
                    Search Timeline Date
                    <input
                      value={timelineSearch}
                      onChange={(event) => setTimelineSearch(event.target.value)}
                      placeholder="YYYY-MM-DD"
                    />
                  </label>
                  <label className="input-stack">
                    Risk Band
                    <select
                      value={timelineRiskFilter}
                      onChange={(event) => setTimelineRiskFilter(event.target.value)}
                    >
                      <option value="all">All</option>
                      <option value="high">High (70%+)</option>
                      <option value="medium">Medium (50-69%)</option>
                      <option value="low">Low (&lt;50%)</option>
                    </select>
                  </label>
                </div>

                {filteredTimelinePoints.length > 0 ? (
                  <div className="simple-list">
                    {filteredTimelinePoints.slice(0, 12).map((point) => (
                      <div key={point.snapshot_date} className="simple-card">
                        <h3>{point.snapshot_date}</h3>
                        <p>
                          Engagement {toPercent(point.engagement_score)} • Attrition {toPercent(point.attrition_risk)} • Burnout {toPercent(point.burnout_risk)}
                        </p>
                        <small>
                          Overtime {point.overtime_hours ?? 0}h • Meetings {point.meeting_hours ?? 0}h • After-hours {point.after_hours_messages ?? 0}
                        </small>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">No timeline records in selected window.</div>
                )}
              </>
            ) : (
              <div className="empty-state">Switch to Advanced View to see full employee timeline and risk history.</div>
            )}
          </Panel>
        </main>
      ) : null}

      {tab === "planning" ? (
        <main className="section-grid">
          <Panel title="Hiring Impact Simulator" subtitle="Estimate financial effect of hiring plans">
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                simulateHiringMutation.mutate(simulationInput);
              }}
            >
              <label className="input-stack">
                Planned hires
                <input
                  type="number"
                  min={0}
                  value={simulationInput.planned_hires}
                  onChange={(event) =>
                    setSimulationInput((prev) => ({ ...prev, planned_hires: Number(event.target.value) }))
                  }
                />
              </label>

              <label className="input-stack">
                Average salary (INR)
                <input
                  type="number"
                  min={0}
                  value={simulationInput.avg_salary}
                  onChange={(event) =>
                    setSimulationInput((prev) => ({ ...prev, avg_salary: Number(event.target.value) }))
                  }
                />
              </label>

              <label className="input-stack">
                Revenue per hire (INR)
                <input
                  type="number"
                  min={0}
                  value={simulationInput.expected_revenue_per_hire}
                  onChange={(event) =>
                    setSimulationInput((prev) => ({ ...prev, expected_revenue_per_hire: Number(event.target.value) }))
                  }
                />
              </label>

              <label className="input-stack">
                Productivity time (months)
                <input
                  type="number"
                  min={0}
                  max={24}
                  value={simulationInput.expected_time_to_productivity_months}
                  onChange={(event) =>
                    setSimulationInput((prev) => ({
                      ...prev,
                      expected_time_to_productivity_months: Number(event.target.value),
                    }))
                  }
                />
              </label>

              <button className="btn" type="submit" disabled={simulateHiringMutation.isPending}>
                {simulateHiringMutation.isPending ? "Calculating..." : "Run Hiring Simulation"}
              </button>
            </form>

            {simulateHiringMutation.data ? (
              <div className="result-grid">
                <MetricCard label="Annual Cost" value={toCurrency(simulateHiringMutation.data.annual_hiring_cost)} />
                <MetricCard label="Revenue Uplift" value={toCurrency(simulateHiringMutation.data.annual_revenue_uplift)} tone="good" />
                <MetricCard label="Net Impact" value={toCurrency(simulateHiringMutation.data.net_impact_year_1)} tone="good" />
                <MetricCard label="Payback (months)" value={simulateHiringMutation.data.payback_months.toFixed(1)} />
              </div>
            ) : null}
          </Panel>

          {showAdvanced ? (
            <Panel title="Compensation Adjustment Simulator" subtitle="Evaluate payroll and retention tradeoffs">
            <div className="filter-row">
              <label className="input-stack">
                Search Department
                <input
                  value={planningDepartmentSearch}
                  onChange={(event) => setPlanningDepartmentSearch(event.target.value)}
                  placeholder="Filter departments"
                />
              </label>
              <label className="input-stack">
                Pick Department
                <select
                  value={compensationInput.department ?? ""}
                  onChange={(event) =>
                    setCompensationInput((prev) => ({ ...prev, department: event.target.value }))
                  }
                >
                  <option value="">All departments</option>
                  {planningDepartmentRows.map((department) => (
                    <option key={department.department} value={department.department}>
                      {department.department}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                simulateCompMutation.mutate(compensationInput);
              }}
            >
              <label className="input-stack">
                Department (optional)
                <input
                  value={compensationInput.department ?? ""}
                  onChange={(event) =>
                    setCompensationInput((prev) => ({ ...prev, department: event.target.value }))
                  }
                  placeholder="Engineering"
                />
              </label>

              <label className="input-stack">
                Adjustment % (e.g. 0.08 = 8%)
                <input
                  type="number"
                  step="0.01"
                  min={-0.5}
                  max={1}
                  value={compensationInput.adjustment_pct}
                  onChange={(event) =>
                    setCompensationInput((prev) => ({ ...prev, adjustment_pct: Number(event.target.value) }))
                  }
                />
              </label>

              <label className="input-stack">
                Expected retention gain %
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={compensationInput.expected_retention_gain_pct}
                  onChange={(event) =>
                    setCompensationInput((prev) => ({ ...prev, expected_retention_gain_pct: Number(event.target.value) }))
                  }
                />
              </label>

              <label className="input-stack">
                Months to realization
                <input
                  type="number"
                  min={0}
                  max={24}
                  value={compensationInput.months_to_realization}
                  onChange={(event) =>
                    setCompensationInput((prev) => ({ ...prev, months_to_realization: Number(event.target.value) }))
                  }
                />
              </label>

              <button className="btn" type="submit" disabled={simulateCompMutation.isPending}>
                {simulateCompMutation.isPending ? "Calculating..." : "Run Compensation Simulation"}
              </button>
            </form>

            {planningDepartmentRows.length > 0 ? (
              <div className="simple-list">
                {planningDepartmentRows.slice(0, 6).map((department) => (
                  <div key={department.department} className="simple-card">
                    <h3>{department.department}</h3>
                    <p>
                      Headcount {department.headcount} • Payroll {toCurrency(department.annual_payroll)}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}

            {simulateCompMutation.data ? (
              <div className="result-grid">
                <MetricCard label="Impacted Headcount" value={String(simulateCompMutation.data.impacted_headcount)} />
                <MetricCard label="Current Payroll" value={toCurrency(simulateCompMutation.data.current_annual_payroll)} />
                <MetricCard label="Incremental Cost" value={toCurrency(simulateCompMutation.data.incremental_annual_cost)} tone="warn" />
                <MetricCard label="Net Year-1 Impact" value={toCurrency(simulateCompMutation.data.net_year_1_impact)} tone="good" />
              </div>
            ) : null}
            </Panel>
          ) : (
            <Panel title="Compensation Adjustment Simulator" subtitle="Advanced planning workspace">
              <div className="empty-state">Switch to Advanced View to use compensation scenario modeling.</div>
            </Panel>
          )}
        </main>
      ) : null}

      {tab === "assistant" ? (
        <main className="section-grid">
          <Panel title="Policy Assistant" subtitle="Ask HR policy questions in plain language">
            {showAdvanced ? (
              <div className="filter-row">
                <label className="input-stack">
                  Search History
                  <input
                    value={assistantHistorySearch}
                    onChange={(event) => setAssistantHistorySearch(event.target.value)}
                    placeholder="Question, answer, citation"
                  />
                </label>
              </div>
            ) : null}

            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                if (!policyQuestion.trim()) {
                  return;
                }
                policyMutation.mutate(policyQuestion);
              }}
            >
              <label className="input-stack span-2">
                Your question
                <textarea
                  value={policyQuestion}
                  onChange={(event) => setPolicyQuestion(event.target.value)}
                  rows={4}
                  placeholder="Example: What is our leave policy for planned vacation?"
                />
              </label>
              <button className="btn" type="submit" disabled={policyMutation.isPending}>
                {policyMutation.isPending ? "Checking..." : "Ask Assistant"}
              </button>
            </form>

            {policyMutation.data ? (
              <div className="policy-answer">
                <p>{policyMutation.data.answer}</p>
                <small>Source: {policyMutation.data.citation}</small>
              </div>
            ) : null}

            {showAdvanced && filteredAssistantHistory.length > 0 ? (
              <div className="simple-list">
                {filteredAssistantHistory.slice(0, 8).map((entry, index) => (
                  <div key={`${entry.createdAt}-${index}`} className="simple-card">
                    <h3>{entry.question}</h3>
                    <p>{entry.answer}</p>
                    <small>
                      {entry.citation} • {toDate(entry.createdAt)}
                    </small>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>
        </main>
      ) : null}

      {tab === "settings" ? (
        <main className="section-grid">
          <Panel title="RBAC Settings" subtitle="Control role-based API access from navbar and sidebar">
            {authContext.isLoading ? <p className="filter-note">Refreshing role permissions...</p> : null}
            <div className="filter-row">
              {!isAuthRequired ? (
                <label className="input-stack">
                  Active Role
                  <select
                    value={userRole}
                    onChange={(event) => setUserRole(event.target.value as UserRole)}
                  >
                    {roleOptions.map((role) => (
                      <option key={role} value={role}>
                        {role.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label className="input-stack">
                  Signed In As
                  <input value={authContext.data?.user?.email ?? loginEmail} readOnly />
                </label>
              )}
              <label className="input-stack">
                Search Permission
                <input
                  value={rbacPermissionSearch}
                  onChange={(event) => setRbacPermissionSearch(event.target.value)}
                  placeholder="insights.read, nudges.write..."
                />
              </label>
            </div>

            <div className="result-grid">
              <MetricCard label="Current Role" value={userRole.replaceAll("_", " ")} />
              <MetricCard label="Granted Permissions" value={String(authContext.data?.permissions.length ?? 0)} />
              <MetricCard label="Allowed Tabs" value={String(availableTabs.length)} />
              <MetricCard label="Blocked Tabs" value={String(Math.max(0, tabs.length - availableTabs.length))} tone="warn" />
            </div>

            <div className="simple-list">
              <div className="simple-card">
                <h3>Sidebar Access by Tab</h3>
                <div className="tab-access-grid">
                  {tabs.map((item) => {
                    const allowed = item.requiredPermissions.every((permission) => canAccess(permission));
                    return (
                      <div key={item.key} className="tab-access-row">
                        <span>{item.label}</span>
                        <strong className={allowed ? "tab-access-allow" : "tab-access-deny"}>
                          {allowed ? "Allowed" : "Blocked"}
                        </strong>
                      </div>
                    );
                  })}
                </div>
              </div>

              {filteredRolePermissions.length === 0 ? (
                <div className="empty-state">No permissions match your search filter.</div>
              ) : (
                filteredRolePermissions.map((entry) => (
                  <div key={entry.role} className="simple-card">
                    <h3>{entry.role.replaceAll("_", " ")}</h3>
                    <div className="permission-chip-group">
                      {entry.permissions.map((permission) => (
                        <span key={`${entry.role}-${permission}`} className="permission-chip">
                          {permission}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>

            {isLoggedIn ? (
              <div className="simple-list">
                <div className="simple-card">
                  <h3>Change Password</h3>
                  <form
                    className="form-grid"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!passwordForm.current_password || !passwordForm.new_password) {
                        return;
                      }
                      changePasswordMutation.mutate();
                    }}
                  >
                    <label className="input-stack">
                      Current Password
                      <input
                        type="password"
                        value={passwordForm.current_password}
                        onChange={(event) =>
                          setPasswordForm((previous) => ({ ...previous, current_password: event.target.value }))
                        }
                      />
                    </label>
                    <label className="input-stack">
                      New Password
                      <input
                        type="password"
                        value={passwordForm.new_password}
                        onChange={(event) =>
                          setPasswordForm((previous) => ({ ...previous, new_password: event.target.value }))
                        }
                      />
                    </label>
                    <button className="btn" type="submit" disabled={changePasswordMutation.isPending}>
                      {changePasswordMutation.isPending ? "Updating..." : "Update Password"}
                    </button>
                  </form>
                </div>
              </div>
            ) : null}

            {canManageUsers ? (
              <div className="simple-list">
                <div className="simple-card">
                  <h3>User Management</h3>
                  <form
                    className="form-grid"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!newUserInput.email || !newUserInput.password || !newUserInput.full_name) {
                        return;
                      }
                      createAuthUserMutation.mutate(newUserInput);
                    }}
                  >
                    <label className="input-stack">
                      Full Name
                      <input
                        value={newUserInput.full_name}
                        onChange={(event) =>
                          setNewUserInput((previous) => ({ ...previous, full_name: event.target.value }))
                        }
                      />
                    </label>
                    <label className="input-stack">
                      Email
                      <input
                        type="email"
                        value={newUserInput.email}
                        onChange={(event) =>
                          setNewUserInput((previous) => ({ ...previous, email: event.target.value }))
                        }
                      />
                    </label>
                    <label className="input-stack">
                      Role
                      <select
                        value={newUserInput.role}
                        onChange={(event) =>
                          setNewUserInput((previous) => ({ ...previous, role: event.target.value as UserRole }))
                        }
                      >
                        {roleOptions.map((role) => (
                          <option key={role} value={role}>
                            {role.replaceAll("_", " ")}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="input-stack">
                      Temporary Password
                      <input
                        type="password"
                        value={newUserInput.password}
                        onChange={(event) =>
                          setNewUserInput((previous) => ({ ...previous, password: event.target.value }))
                        }
                      />
                    </label>
                    <button className="btn" type="submit" disabled={createAuthUserMutation.isPending}>
                      {createAuthUserMutation.isPending ? "Creating..." : "Create User"}
                    </button>
                  </form>
                </div>

                {authUsersQuery.data?.map((authUser) => (
                  <div key={authUser.id} className="simple-card">
                    <h3>{authUser.full_name}</h3>
                    <p>{authUser.email}</p>
                    <small>Current role: {authUser.role.replaceAll("_", " ")}</small>
                    <div className="filter-row">
                      <label className="input-stack">
                        Update Role
                        <select
                          value={authUser.role}
                          onChange={(event) =>
                            updateAuthRoleMutation.mutate({
                              userId: authUser.id,
                              role: event.target.value as UserRole,
                            })
                          }
                        >
                          {roleOptions.map((role) => (
                            <option key={`${authUser.id}-${role}`} value={role}>
                              {role.replaceAll("_", " ")}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="input-stack">
                        Reset Password
                        <input
                          type="password"
                          value={adminResetPasswords[authUser.id] ?? ""}
                          onChange={(event) =>
                            setAdminResetPasswords((previous) => ({
                              ...previous,
                              [authUser.id]: event.target.value,
                            }))
                          }
                          placeholder="New temporary password"
                        />
                      </label>
                      <div className="input-stack">
                        <span>Apply</span>
                        <button
                          className="btn secondary"
                          type="button"
                          disabled={
                            resetAuthPasswordMutation.isPending
                            || !(adminResetPasswords[authUser.id]?.trim())
                          }
                          onClick={() =>
                            resetAuthPasswordMutation.mutate({
                              userId: authUser.id,
                              newPassword: (adminResetPasswords[authUser.id] ?? "").trim(),
                            })
                          }
                        >
                          Reset Password
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>
        </main>
      ) : null}
        </div>
      </div>
      {employeeProfileModalOpen ? (
        <div className="modal-overlay" onClick={closeEmployeeProfileModal}>
          <section className="modal-card" onClick={(event) => event.stopPropagation()}>
            <header className="modal-header">
              <div>
                <h3>{employeeProfileModalMode === "create" ? "Create Employee Profile" : "Edit Employee Profile"}</h3>
                <p>Upload image, update profile fields, and save changes.</p>
              </div>
              <button className="btn secondary" type="button" onClick={closeEmployeeProfileModal}>
                Close
              </button>
            </header>

            <form
              className="modal-form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                submitEmployeeProfileForm();
              }}
            >
              <label className="input-stack">
                External ID*
                <input
                  required
                  value={employeeProfileForm.external_id}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, external_id: event.target.value }))
                  }
                  placeholder="EMP-1001"
                />
              </label>
              <label className="input-stack">
                Full Name*
                <input
                  required
                  value={employeeProfileForm.full_name}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, full_name: event.target.value }))
                  }
                  placeholder="Aarav Sharma"
                />
              </label>
              <label className="input-stack">
                Email*
                <input
                  required
                  type="email"
                  value={employeeProfileForm.email}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, email: event.target.value }))
                  }
                  placeholder="aarav@example.com"
                />
              </label>
              <label className="input-stack">
                Manager ID
                <input
                  type="number"
                  min={1}
                  value={employeeProfileForm.manager_id}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, manager_id: event.target.value }))
                  }
                  placeholder="Optional manager ID"
                />
              </label>
              <label className="input-stack">
                Department*
                <input
                  required
                  value={employeeProfileForm.department}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, department: event.target.value }))
                  }
                  placeholder="Engineering"
                />
              </label>
              <label className="input-stack">
                Role*
                <input
                  required
                  value={employeeProfileForm.role}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, role: event.target.value }))
                  }
                  placeholder="Senior Engineer"
                />
              </label>
              <label className="input-stack">
                Location*
                <input
                  required
                  value={employeeProfileForm.location}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, location: event.target.value }))
                  }
                  placeholder="Bengaluru"
                />
              </label>
              <label className="input-stack">
                Hire Date*
                <input
                  required
                  type="date"
                  value={employeeProfileForm.hire_date}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, hire_date: event.target.value }))
                  }
                />
              </label>
              <label className="input-stack">
                Employment Status
                <select
                  value={employeeProfileForm.employment_status}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, employment_status: event.target.value }))
                  }
                >
                  <option value="active">Active</option>
                  <option value="on_leave">On Leave</option>
                  <option value="inactive">Inactive</option>
                  <option value="terminated">Terminated</option>
                </select>
              </label>
              <label className="input-stack">
                Base Salary
                <input
                  type="number"
                  min={0}
                  value={employeeProfileForm.base_salary}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, base_salary: event.target.value }))
                  }
                />
              </label>
              <label className="input-stack">
                Preferred Name
                <input
                  value={employeeProfileForm.preferred_name}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, preferred_name: event.target.value }))
                  }
                  placeholder="Aarav"
                />
              </label>
              <label className="input-stack">
                Phone
                <input
                  value={employeeProfileForm.phone}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, phone: event.target.value }))
                  }
                  placeholder="+91 98765 43210"
                />
              </label>
              <label className="input-stack">
                Emergency Contact Name
                <input
                  value={employeeProfileForm.emergency_contact_name}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, emergency_contact_name: event.target.value }))
                  }
                  placeholder="Name"
                />
              </label>
              <label className="input-stack">
                Emergency Contact Phone
                <input
                  value={employeeProfileForm.emergency_contact_phone}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, emergency_contact_phone: event.target.value }))
                  }
                  placeholder="+91 90000 00000"
                />
              </label>
              <label className="input-stack">
                Date of Birth
                <input
                  type="date"
                  value={employeeProfileForm.date_of_birth}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, date_of_birth: event.target.value }))
                  }
                />
              </label>
              <label className="input-stack span-2">
                Address
                <input
                  value={employeeProfileForm.address}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, address: event.target.value }))
                  }
                  placeholder="Address"
                />
              </label>
              <label className="input-stack span-2">
                Skills
                <input
                  value={employeeProfileForm.skills}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, skills: event.target.value }))
                  }
                  placeholder="People strategy, analytics, SQL, leadership"
                />
              </label>
              <label className="input-stack span-2">
                Bio
                <textarea
                  rows={3}
                  value={employeeProfileForm.bio}
                  onChange={(event) =>
                    setEmployeeProfileForm((previous) => ({ ...previous, bio: event.target.value }))
                  }
                  placeholder="Short profile summary"
                />
              </label>
              <div className="modal-avatar-block span-2">
                <label className="input-stack">
                  Profile Image (Base64 preview)
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        handleEmployeeAvatarUpload(file);
                      }
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
                {employeeProfileForm.avatar_image_base64 ? (
                  <div className="modal-avatar-preview-wrap">
                    <img
                      className="modal-avatar-preview"
                      src={employeeProfileForm.avatar_image_base64}
                      alt="Employee avatar preview"
                    />
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() =>
                        setEmployeeProfileForm((previous) => ({ ...previous, avatar_image_base64: "" }))
                      }
                    >
                      Remove Image
                    </button>
                  </div>
                ) : (
                  <div className="empty-state">No image selected yet.</div>
                )}
              </div>
              <div className="modal-actions span-2">
                <button className="btn secondary" type="button" onClick={closeEmployeeProfileModal}>
                  Cancel
                </button>
                <button
                  className="btn"
                  type="submit"
                  disabled={createEmployeeMutation.isPending || updateEmployeeMutation.isPending}
                >
                  {createEmployeeMutation.isPending || updateEmployeeMutation.isPending
                    ? "Saving..."
                    : employeeProfileModalMode === "create"
                      ? "Create Profile"
                      : "Save Changes"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
      {employeeDeleteModalOpen ? (
        <div className="modal-overlay" onClick={() => setEmployeeDeleteModalOpen(false)}>
          <section className="modal-card modal-card-sm" onClick={(event) => event.stopPropagation()}>
            <header className="modal-header">
              <div>
                <h3>Delete Employee Profile</h3>
                <p>
                  This will deactivate{" "}
                  <strong>{employeeProfile.data?.employee.full_name ?? "this employee"}</strong> and remove it from active lists.
                </p>
              </div>
            </header>
            <div className="modal-actions">
              <button className="btn secondary" type="button" onClick={() => setEmployeeDeleteModalOpen(false)}>
                Cancel
              </button>
              <button
                className="btn danger"
                type="button"
                disabled={!employeeProfile.data || deleteEmployeeMutation.isPending}
                onClick={() => {
                  if (!employeeProfile.data) {
                    return;
                  }
                  deleteEmployeeMutation.mutate(employeeProfile.data.employee.id);
                }}
              >
                {deleteEmployeeMutation.isPending ? "Deleting..." : "Confirm Delete"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      </motion.div>
    </div>
  );
}
