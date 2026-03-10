# Scaling Guide (1 Crore Employees)

This codebase now includes structural changes for high-scale operation:

- Precomputed `employee_risk_snapshots` table.
- Batched refresh pipeline (`refresh_risk_snapshots`) using keyset iteration.
- Paginated risk and nudge APIs.
- Bounded ONA reads (`/insights/ona-from-db?limit=...`).
- Indexed risk snapshot and nudge query paths.

## What this Enables

- Request latency stays stable because risk calculations are not done on every API call.
- Org-health and risk APIs use aggregate/select queries, not employee loops.
- Nudge generation runs against precomputed snapshots.

## Production Setup Required for 1 Crore Scale

1. Postgres partitioning and read replicas.
2. Background worker/scheduler to run snapshot refresh incrementally.
3. Redis-backed distributed rate limiting (replace in-memory limiter).
4. Async job queue for nudge generation and notification delivery.
5. Observability with SLO alerts (p95 latency, queue lag, replication lag).
6. Blue/green deploys and migration strategy.

## Recommended Refresh Pattern

- Trigger `refresh_risk_snapshots` every 5-15 minutes for changed employees.
- Use `only_employee_ids` batches from ingestion events.
- Keep batch size in the 2k-20k range depending on DB capacity.

## API Practices

- Always use pagination on:
  - `/api/v1/insights/risks`
  - `/api/v1/nudges`
  - `/api/v1/insights/ona-from-db`
- Avoid unbounded reads for any endpoint in production.
