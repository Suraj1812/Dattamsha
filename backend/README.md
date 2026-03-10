# Backend

FastAPI backend for workforce intelligence, including:
- unified employee model
- dynamic workforce ingestion API
- precomputed risk snapshots (batch refresh)
- trend, cohort, anomaly analytics
- manager team overview
- workforce finance analytics
- paginated risk insights and employee timeline
- nudge engine with dispatch + feedback tracking
- ONA analytics
- hiring + compensation simulations
- policy assistant with section-level citation
- JWT login + refresh tokens + RBAC

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

Refresh risk snapshots (batch mode):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/insights/refresh-risk-snapshots?batch_size=5000" \
  -H "X-API-Key: <key-if-enabled>"
```

Dynamic ingestion example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/ingest/workforce" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <key-if-enabled>" \
  -d '{
    "source": "hris-api",
    "employees": [
      {
        "external_id": "E1001",
        "full_name": "Riya Verma",
        "email": "riya.verma@example.com",
        "manager_external_id": null,
        "department": "Engineering",
        "role": "Engineering Manager",
        "location": "Bengaluru",
        "hire_date": "2022-01-10",
        "employment_status": "active",
        "base_salary": 2200000
      }
    ],
    "engagement_metrics": [],
    "workload_metrics": [],
    "performance_metrics": [],
    "collaboration_edges": []
  }'
```

Key endpoints:

- `GET /api/v1/insights/trends`
- `GET /api/v1/insights/cohorts?dimension=department`
- `GET /api/v1/insights/anomalies?dimension=department`
- `GET /api/v1/managers/{manager_id}/team-overview`
- `GET /api/v1/analytics/workforce-finance`
- `GET /api/v1/employees/{employee_id}/timeline`
- `POST /api/v1/nudges/dispatch`
- `POST /api/v1/nudges/{nudge_id}/feedback`
- `POST /api/v1/employees/{employee_id}/consents`
- `GET /api/v1/employees/{employee_id}/consents`
- `GET /api/v1/compliance/audit-events`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/users`
- `PATCH /api/v1/auth/users/{user_id}/role`

Compliance controls:

- `ENFORCE_NUDGE_CONSENT=true` prevents nudge generation unless latest
  `consent_type=nudge_engine` status is `granted` for that employee.
- Audit trail records are stored for ingestion, snapshot refresh,
  nudge generation, dispatch, resolve, and feedback actions.

## Checks

```bash
python -m ruff check .
python -m pytest -q
```
