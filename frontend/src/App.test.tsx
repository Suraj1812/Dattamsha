import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import App from "@/App";

vi.mock("@/lib/api", () => {
  return {
    ApiError: class extends Error {},
    api: {
      health: () => Promise.resolve({ status: "ok" }),
      ingestSample: () => Promise.resolve({ source: "sample", employees_loaded: 12, metrics_loaded: 51 }),
      orgHealth: () => Promise.resolve({
        active_headcount: 12,
        average_engagement: 0.67,
        average_sentiment: 0.63,
        high_attrition_risk_count: 2,
        high_burnout_risk_count: 2,
      }),
      risks: () => Promise.resolve([]),
      headcountByDepartment: () => Promise.resolve({ Engineering: 6, HR: 2 }),
      ona: () => Promise.resolve({ most_central_employee_ids: [1], most_isolated_employee_ids: [2], average_degree: 2 }),
      nudges: () => Promise.resolve([]),
      generateNudges: () => Promise.resolve([]),
      resolveNudge: () => Promise.resolve({}),
      employeeProfile: () => Promise.resolve({
        employee: {
          id: 1,
          external_id: "E001",
          full_name: "Aarav Sharma",
          email: "aarav.sharma@dattamsha.com",
          manager_id: null,
          department: "Executive",
          role: "CEO",
          location: "Bengaluru",
          hire_date: "2018-01-10",
          employment_status: "active",
          base_salary: 2400000,
        },
        engagement_score: 0.8,
        sentiment_score: 0.7,
        overtime_hours: 6,
        meeting_hours: 18,
        performance_rating: 0.86,
        goal_completion_pct: 0.9,
        attrition_risk: 0.14,
        burnout_risk: 0.22,
      }),
      simulateHiring: () => Promise.resolve({
        annual_hiring_cost: 1,
        annual_revenue_uplift: 2,
        net_impact_year_1: 1,
        payback_months: 6,
      }),
      policyQuery: () => Promise.resolve({ answer: "policy", citation: "docs" }),
    },
  };
});

function renderApp() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders dashboard title", async () => {
    renderApp();
    expect(screen.getByText(/Workforce Intelligence Console/i)).toBeInTheDocument();
  });
});
