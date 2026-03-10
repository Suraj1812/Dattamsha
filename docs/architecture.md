# Architecture Mapping to Deck

## Layer 1: HR Systems and Integrations
- Sources: HRIS, Payroll, ATS, LMS, Engagement tools, Business apps.
- MVP implementation: CSV-based adapter in `backend/app/services/ingest.py` with replacement points for API connectors.

## Layer 2: Data and Context Layer
- Canonical employee identity model and domain entities in SQLAlchemy.
- Data quality and governance placeholders included in ingest flow.

## Layer 3: Data Layer
- SQLite for local dev, Postgres for runtime scaling.
- dbt scaffolding for staging and mart models in `backend/dbt/models`.

## Layer 4: Analytics and Intelligence Layer
- Employee risk scoring: attrition and burnout scores.
- ONA graph analytics using NetworkX.
- Financial decision simulation endpoint.

## Layer 5: Consumption Layer
- FastAPI endpoints for role-facing integrations (dashboards, bots, manager portals).
- Nudge engine for proactive insight delivery.
- Policy assistant endpoint for conversational HR access.

## Cross-Cutting Concerns
- Privacy: configurable RBAC and data access boundaries (to be integrated with enterprise IAM).
- Compliance: model supports auditable nudges and decision evidence.
- Extensibility: Airflow and dbt are included as orchestration and transformation scaffolds.
