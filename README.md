# Dattamsha Platform

Clean monorepo structure:

- `backend/` FastAPI + data fabric + analytics + nudge engine
- `frontend/` React + Vite dashboard
- `docs/` architecture and production notes
- `docker-compose.yml` full-stack local deployment

## Folder Layout

```text
Dattamsha/
  backend/
    app/
    airflow/
    dbt/
    samples/
    policies/
    tests/
    pyproject.toml
    Dockerfile
    Makefile
    .env.example
  frontend/
    src/
    package.json
    Dockerfile
    .env.example
  docs/
  docker-compose.yml
```

## Backend (local)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000/api/v1`

High-scale refresh endpoint:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/insights/refresh-risk-snapshots?batch_size=5000"
```

## Frontend (local)

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

UI: `http://127.0.0.1:5173`

## Full Stack (Docker)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- API: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:8080`

## Validation

Backend:
```bash
cd backend
python -m ruff check .
python -m pytest -q
```

Frontend:
```bash
cd frontend
npm run lint
npm run test
npm run build
```

Scaling reference: [docs/scaling.md](/Users/surajsingh/Documents/Dattamsha/docs/scaling.md)
