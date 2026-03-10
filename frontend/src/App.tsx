import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { AlertTriangle, RefreshCcw, Search, Sparkles } from "lucide-react";

import { MetricCard } from "@/components/MetricCard";
import { Panel } from "@/components/Panel";
import { StatusBanner } from "@/components/StatusBanner";
import { useDashboardData } from "@/hooks/useDashboardData";
import { api, ApiError } from "@/lib/api";
import { appConfig } from "@/lib/config";
import { toCompactNumber, toCurrency, toDate, toPercent } from "@/lib/format";
import type { HiringSimulationRequest } from "@/lib/types";

const CHART_COLORS = ["#0f6b5b", "#f08c46", "#1f91b7", "#b6482d", "#4f7d29", "#9c6a2f"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}${error.requestId ? ` (request: ${error.requestId})` : ""}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

export default function App() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("dattamsha.apiKey") ?? appConfig.defaultApiKey);
  const [employeeId, setEmployeeId] = useState(appConfig.defaultEmployeeId);
  const [policyQuestion, setPolicyQuestion] = useState("How many paid leave days are available?");
  const [notice, setNotice] = useState<string>("");

  const [simulationInput, setSimulationInput] = useState<HiringSimulationRequest>({
    planned_hires: 6,
    avg_salary: 1200000,
    expected_revenue_per_hire: 2400000,
    expected_time_to_productivity_months: 4,
  });

  useEffect(() => {
    localStorage.setItem("dattamsha.apiKey", apiKey);
  }, [apiKey]);

  const data = useDashboardData(apiKey);

  const employeeProfile = useQuery({
    queryKey: ["employeeProfile", employeeId, apiKey],
    queryFn: () => api.employeeProfile(employeeId, apiKey),
    enabled: Number.isFinite(employeeId) && employeeId > 0,
    retry: 1,
  });

  const simulateMutation = useMutation({
    mutationFn: (payload: HiringSimulationRequest) => api.simulateHiring(payload, apiKey),
  });

  const policyMutation = useMutation({
    mutationFn: (question: string) => api.policyQuery(question, apiKey),
  });

  const ingestMutation = useMutation({
    mutationFn: () => api.ingestSample(apiKey),
    onSuccess: () => {
      setNotice("Sample data ingested successfully.");
      void queryClient.invalidateQueries();
    },
  });

  const generateNudgeMutation = useMutation({
    mutationFn: () => api.generateNudges(apiKey),
    onSuccess: () => {
      setNotice("Nudge generation completed.");
      void queryClient.invalidateQueries({ queryKey: ["nudges", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["risks", apiKey] });
      void queryClient.invalidateQueries({ queryKey: ["orgHealth", apiKey] });
    },
  });

  const resolveNudgeMutation = useMutation({
    mutationFn: (id: number) => api.resolveNudge(id, apiKey),
    onSuccess: () => {
      setNotice("Nudge marked as resolved.");
      void queryClient.invalidateQueries({ queryKey: ["nudges", apiKey] });
    },
  });

  const headcountChartData = useMemo(() => {
    if (!data.headcountByDepartment.data) {
      return [];
    }
    return Object.entries(data.headcountByDepartment.data).map(([department, count]) => ({
      department,
      count,
    }));
  }, [data.headcountByDepartment.data]);

  const riskChartData = useMemo(() => {
    return (data.risks.data ?? []).slice(0, 8).map((row) => ({
      name: row.employee_name,
      attrition: Number((row.attrition_risk * 100).toFixed(1)),
      burnout: Number((row.burnout_risk * 100).toFixed(1)),
    }));
  }, [data.risks.data]);

  const loadingInitial =
    data.orgHealth.isLoading || data.risks.isLoading || data.nudges.isLoading || data.headcountByDepartment.isLoading;

  const hasApiError = [
    data.orgHealth.error,
    data.risks.error,
    data.nudges.error,
    data.ona.error,
    employeeProfile.error,
  ].find(Boolean);

  return (
    <div className="app-shell">
      <div className="ambient-glow" aria-hidden="true" />
      <header className="topbar">
        <div className="title-block">
          <p className="eyebrow">Dattamsha Data Labs</p>
          <h1>Workforce Intelligence Console</h1>
          <p className="subtitle">
            Unified HR analytics, risk signals, managerial nudges, and workforce finance simulation.
          </p>
        </div>

        <div className="topbar-actions">
          <label className="input-stack">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="Optional if backend is open"
            />
          </label>
          <label className="input-stack small">
            Employee ID
            <input
              type="number"
              min={1}
              value={employeeId}
              onChange={(event) => setEmployeeId(Number(event.target.value))}
            />
          </label>
          <button
            className="btn secondary"
            onClick={() => {
              setNotice("");
              void queryClient.invalidateQueries();
            }}
          >
            <RefreshCcw size={16} /> Refresh
          </button>
          <button className="btn" onClick={() => ingestMutation.mutate()} disabled={ingestMutation.isPending}>
            {ingestMutation.isPending ? "Ingesting..." : "Seed/Refresh Data"}
          </button>
        </div>
      </header>

      {data.health.data?.status === "ok" ? (
        <StatusBanner type="ok" message="Backend is reachable." />
      ) : null}

      {notice ? <StatusBanner type="ok" message={notice} /> : null}

      {hasApiError ? <StatusBanner type="error" message={errorMessage(hasApiError)} /> : null}

      {loadingInitial ? <p className="loading">Loading workforce intelligence data...</p> : null}

      <main className="dashboard-grid">
        <section className="metrics-row reveal">
          <MetricCard
            label="Active Headcount"
            value={toCompactNumber(data.orgHealth.data?.active_headcount ?? 0)}
            hint="From unified employee master"
            tone="neutral"
          />
          <MetricCard
            label="Avg Engagement"
            value={toPercent(data.orgHealth.data?.average_engagement)}
            hint="Latest pulse + survey signals"
            tone="good"
          />
          <MetricCard
            label="High Attrition Risk"
            value={String(data.orgHealth.data?.high_attrition_risk_count ?? 0)}
            hint="Threshold-driven prioritization"
            tone="warn"
          />
          <MetricCard
            label="High Burnout Risk"
            value={String(data.orgHealth.data?.high_burnout_risk_count ?? 0)}
            hint="Workload + after-hours pattern"
            tone="warn"
          />
        </section>

        <Panel title="Department Mix" subtitle="Current active headcount split by department" className="reveal delay-1">
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={headcountChartData}
                  dataKey="count"
                  nameKey="department"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  innerRadius={50}
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

        <Panel
          title="Risk Radar"
          subtitle="Top high-risk employees by attrition and burnout"
          className="reveal delay-2"
        >
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={riskChartData}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4c9ba" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} height={56} textAnchor="end" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="attrition" fill="#0f6b5b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="burnout" fill="#f08c46" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title="Nudge Engine"
          subtitle="Action queue for managers and HR"
          className="reveal delay-3"
          actions={
            <button
              className="btn"
              onClick={() => generateNudgeMutation.mutate()}
              disabled={generateNudgeMutation.isPending}
            >
              <Sparkles size={16} />
              {generateNudgeMutation.isPending ? "Generating..." : "Generate Nudges"}
            </button>
          }
        >
          <div className="nudge-list">
            {(data.nudges.data ?? []).length === 0 ? (
              <div className="empty-state">No open nudges right now.</div>
            ) : (
              data.nudges.data?.map((nudge) => (
                <article key={nudge.id} className={`nudge-item severity-${nudge.severity}`}>
                  <div>
                    <p className="nudge-title">#{nudge.id} {nudge.nudge_type.replaceAll("_", " ")}</p>
                    <p>{nudge.message}</p>
                    <small>{nudge.evidence}</small>
                    <small>Created: {toDate(nudge.created_at)}</small>
                  </div>
                  <button
                    className="btn secondary"
                    onClick={() => resolveNudgeMutation.mutate(nudge.id)}
                    disabled={resolveNudgeMutation.isPending}
                  >
                    Resolve
                  </button>
                </article>
              ))
            )}
          </div>
        </Panel>

        <Panel
          title="Employee Explorer"
          subtitle="Unified profile view with risk and performance signals"
          className="reveal delay-4"
          actions={
            <button className="btn secondary" onClick={() => employeeProfile.refetch()}>
              <Search size={16} />
              Load Employee
            </button>
          }
        >
          {employeeProfile.data ? (
            <div className="profile-grid">
              <div>
                <h3>{employeeProfile.data.employee.full_name}</h3>
                <p>{employeeProfile.data.employee.role} • {employeeProfile.data.employee.department}</p>
                <p>{employeeProfile.data.employee.location}</p>
              </div>
              <MetricCard label="Attrition Risk" value={toPercent(employeeProfile.data.attrition_risk)} tone="warn" />
              <MetricCard label="Burnout Risk" value={toPercent(employeeProfile.data.burnout_risk)} tone="warn" />
              <MetricCard label="Engagement" value={toPercent(employeeProfile.data.engagement_score)} tone="good" />
              <MetricCard
                label="Goal Completion"
                value={toPercent(employeeProfile.data.goal_completion_pct)}
                tone="neutral"
              />
            </div>
          ) : (
            <div className="empty-state">Load an employee profile using the Employee ID field.</div>
          )}
        </Panel>

        <Panel
          title="Decision Simulation"
          subtitle="Estimate hiring plan impact on cost and payback"
          className="reveal delay-5"
        >
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              simulateMutation.mutate(simulationInput);
            }}
          >
            <label className="input-stack">
              Planned Hires
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
              Avg Salary (INR)
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
              Expected Revenue per Hire (INR)
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
              Time to Productivity (months)
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

            <button className="btn" type="submit" disabled={simulateMutation.isPending}>
              {simulateMutation.isPending ? "Calculating..." : "Run Simulation"}
            </button>
          </form>

          {simulateMutation.data ? (
            <div className="sim-results">
              <MetricCard label="Annual Hiring Cost" value={toCurrency(simulateMutation.data.annual_hiring_cost)} />
              <MetricCard label="Year-1 Revenue Uplift" value={toCurrency(simulateMutation.data.annual_revenue_uplift)} tone="good" />
              <MetricCard label="Net Impact" value={toCurrency(simulateMutation.data.net_impact_year_1)} tone="good" />
              <MetricCard label="Payback (months)" value={simulateMutation.data.payback_months.toFixed(1)} />
            </div>
          ) : null}
        </Panel>

        <Panel
          title="Policy Assistant"
          subtitle="Ask policy questions with quick evidence"
          className="reveal delay-6"
        >
          <form
            className="policy-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!policyQuestion.trim()) {
                return;
              }
              policyMutation.mutate(policyQuestion);
            }}
          >
            <textarea
              value={policyQuestion}
              onChange={(event) => setPolicyQuestion(event.target.value)}
              rows={4}
              placeholder="Ask a question about leave, wellbeing, or code of conduct..."
            />
            <button className="btn" type="submit" disabled={policyMutation.isPending}>
              {policyMutation.isPending ? "Thinking..." : "Ask Assistant"}
            </button>
          </form>

          {policyMutation.data ? (
            <div className="policy-answer">
              <p>{policyMutation.data.answer}</p>
              <small>Citation: {policyMutation.data.citation}</small>
            </div>
          ) : null}
        </Panel>

        <Panel title="Organizational Network Signals" subtitle="Collaboration topology summary" className="reveal delay-7">
          {data.ona.data ? (
            <div className="ona-grid">
              <MetricCard label="Avg Degree" value={data.ona.data.average_degree.toFixed(2)} />
              <div>
                <h3>Most Central Employees</h3>
                <p>{data.ona.data.most_central_employee_ids.join(", ") || "-"}</p>
              </div>
              <div>
                <h3>Most Isolated Employees</h3>
                <p>{data.ona.data.most_isolated_employee_ids.join(", ") || "-"}</p>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <AlertTriangle size={16} /> ONA data unavailable.
            </div>
          )}
        </Panel>
      </main>
    </div>
  );
}
