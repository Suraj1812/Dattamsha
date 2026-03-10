# Dattamsha HR Intelligence Platform

This repository is a production-ready full-stack baseline for the architecture described in the Dattamsha pitch deck:
- Unified HR data fabric (ingest + model)
- Analytics and intelligence APIs
- Employee nudge engine
- Organizational network analysis (ONA)
- Financial workforce simulation
- Policy assistant interface
- Security, readiness checks, request tracing, and rate limiting
- Responsive workforce intelligence frontend dashboard

## 1) Quick Start (Backend)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

API base URL: `http://127.0.0.1:8000/api/v1`

## 2) Quick Start (Frontend)

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

If API key protection is enabled, pass the `X-API-Key` header:

```bash
curl -H "X-API-Key: <your-key>" http://127.0.0.1:8000/api/v1/insights/org-health
```

The frontend also supports API key via `frontend/.env`:
- `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`
- `VITE_API_KEY=<optional>`

## 3) Quick Start (Full Stack with Docker)

```bash
docker compose up --build
```

Services:
- Backend API: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:8080`

Then seed data from local shell:

```bash
python -m app.scripts.seed_data
```

## 4) Core Endpoints

- `GET /api/v1/health`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/ingest/sample`
- `GET /api/v1/employees/{employee_id}/profile`
- `GET /api/v1/insights/org-health`
- `GET /api/v1/insights/risks`
- `GET /api/v1/insights/headcount-by-department`
- `POST /api/v1/insights/ona`
- `GET /api/v1/insights/ona-from-db`
- `POST /api/v1/nudges/generate`
- `GET /api/v1/nudges`
- `POST /api/v1/nudges/{nudge_id}/resolve`
- `POST /api/v1/simulations/hiring-impact`
- `POST /api/v1/assistant/policy-query`

## 5) Runtime Hardening

Included now:
- API key enforcement for non-health endpoints.
- Request ID and process-time headers.
- Security response headers.
- Per-IP rate limiting.
- Trusted host checks.
- Liveness and readiness probes.
- Structured JSON logging.
- GZip response compression.

## 6) Data Model
- `employees`
- `engagement_metrics`
- `workload_metrics`
- `performance_metrics`
- `collaboration_edges`
- `nudges`

## 7) Project Structure

```text
app/
  api/           # FastAPI routes
  core/          # settings
  db/            # SQLAlchemy setup/init
  models/        # ORM entities
  schemas/       # Pydantic schemas
  services/      # analytics, nudges, ONA, simulation, policy assistant
  scripts/       # seed scripts
samples/         # sample HR datasets
policies/        # policy docs used by assistant
airflow/dags/    # data-fabric orchestration scaffold
dbt/             # transformation scaffolding
docs/            # architecture and implementation notes
frontend/        # React + Vite dashboard
```

## 8) Frontend Quality Gates

```bash
cd frontend
npm run lint
npm run test
npm run build
```

## 9) Production Checklist

1. Set `ENVIRONMENT=prod`.
2. Set `ENABLE_DOCS=false`.
3. Set `REQUIRE_API_KEY=true` and a strong `API_KEY`.
4. Set `AUTO_CREATE_SCHEMA=false`.
5. Point `DATABASE_URL` to managed Postgres.
6. Set strict `TRUSTED_HOSTS` and `ALLOWED_ORIGINS`.
7. Run `make preflight`.

Full guide: [docs/production.md](/Users/surajsingh/Documents/Dattamsha/docs/production.md)

## 10) Next Engineering Steps

1. Replace sample CSV ingestor with real API connectors (Workday, DarwinBox, ADP, ATS, LMS).
2. Add incremental ingestion + CDC + idempotency keys.
3. Move heuristic risk scoring to trained models with feature store and model registry.
4. Add event bus (Kafka/SQS) for real-time nudges.
5. Integrate Slack/Teams channels and feedback loop for nudge effectiveness.
6. Add proper RAG stack for policy assistant (vector store + access controls + citations).
