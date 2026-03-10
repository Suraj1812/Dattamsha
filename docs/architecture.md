# Architecture Mapping to Deck

## Layer 1: HR Systems and Integrations
- Sources: HRIS, Payroll, ATS, LMS, Engagement tools, Business apps.
- Runtime implementation: dynamic ingestion API (`POST /api/v1/ingest/workforce`) for employees, metrics, and collaboration edges.

## Layer 2: Data and Context Layer
- Canonical employee identity model and domain entities in SQLAlchemy.
- Data quality and governance checks are enforced at schema and API validation layers.

## Layer 3: Data Layer
- SQLite for local dev, Postgres for runtime scaling.
- dbt scaffolding for staging and mart models in `backend/dbt/models`.

## Layer 4: Analytics and Intelligence Layer
- Employee risk scoring: attrition and burnout scores.
- Trend analytics (`/insights/trends`), cohort analytics (`/insights/cohorts`), anomaly detection (`/insights/anomalies`).
- Manager team analytics (`/managers/{manager_id}/team-overview`).
- ONA graph analytics using NetworkX.
- Workforce finance analytics (`/analytics/workforce-finance`).
- Financial decision simulations: hiring impact + compensation adjustment.

## Layer 5: Consumption Layer
- FastAPI endpoints for role-facing integrations (dashboards, bots, manager portals).
- Nudge engine for proactive insight delivery, dispatch channel support (`/nudges/dispatch`), and feedback capture.
- Policy assistant endpoint for conversational HR access.

## Cross-Cutting Concerns
- Privacy: configurable RBAC and data access boundaries (to be integrated with enterprise IAM).
- Compliance: model supports auditable nudges and decision evidence.
- Extensibility: Airflow and dbt are included as orchestration and transformation scaffolds.
