import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useDashboardData(apiKey: string) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    staleTime: 60_000,
    retry: 1,
  });

  const orgHealth = useQuery({
    queryKey: ["orgHealth", apiKey],
    queryFn: () => api.orgHealth(apiKey),
    staleTime: 60_000,
    retry: 2,
  });

  const risks = useQuery({
    queryKey: ["risks", apiKey],
    queryFn: () => api.risks(apiKey),
    staleTime: 60_000,
    retry: 1,
  });

  const headcountByDepartment = useQuery({
    queryKey: ["headcount", apiKey],
    queryFn: () => api.headcountByDepartment(apiKey),
    staleTime: 60_000,
    retry: 1,
  });

  const ona = useQuery({
    queryKey: ["ona", apiKey],
    queryFn: () => api.ona(apiKey),
    staleTime: 60_000,
    retry: 1,
  });

  const nudges = useQuery({
    queryKey: ["nudges", apiKey],
    queryFn: () => api.nudges(apiKey),
    staleTime: 10_000,
    retry: 1,
  });

  return {
    health,
    orgHealth,
    risks,
    headcountByDepartment,
    ona,
    nudges,
  };
}
