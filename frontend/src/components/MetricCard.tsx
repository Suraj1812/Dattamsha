import clsx from "clsx";

type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "good" | "warn";
};

export function MetricCard({ label, value, hint, tone = "neutral" }: MetricCardProps) {
  return (
    <article className={clsx("metric-card", `metric-${tone}`)}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {hint ? <span className="metric-hint">{hint}</span> : null}
    </article>
  );
}
