import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UserRole } from "@/lib/types";

const PERMISSIONS: Record<UserRole, string[]> = {
  admin: ["insights.read", "employees.read"],
  hr_admin: ["insights.read", "employees.read"],
  manager: ["insights.read", "employees.read"],
  analyst: ["insights.read", "employees.read"],
  employee: [],
};

export function useDashboardData(apiKey: string, userRole: string) {
  const scopedRole = (userRole as UserRole) in PERMISSIONS ? (userRole as UserRole) : "employee";
  const canReadInsights = PERMISSIONS[scopedRole].includes("insights.read");
  const canReadEmployees = PERMISSIONS[scopedRole].includes("employees.read");

  const health = useQuery({
    queryKey: ["health", userRole],
    queryFn: () => api.health(),
    staleTime: 60_000,
    retry: 1,
  });

  const orgHealth = useQuery({
    queryKey: ["orgHealth", apiKey, userRole],
    queryFn: () => api.orgHealth(apiKey),
    enabled: canReadInsights,
    staleTime: 60_000,
    retry: 2,
  });

  const headcountByDepartment = useQuery({
    queryKey: ["headcount", apiKey, userRole],
    queryFn: () => api.headcountByDepartment({}, apiKey),
    enabled: canReadInsights,
    staleTime: 60_000,
    retry: 1,
  });

  const employees = useQuery({
    queryKey: ["employees", apiKey, userRole],
    queryFn: () => api.employees({}, apiKey),
    enabled: canReadEmployees,
    staleTime: 60_000,
    retry: 1,
  });

  return {
    health,
    orgHealth,
    headcountByDepartment,
    employees,
  };
}
