# Backend

FastAPI backend for workforce intelligence, including:
- unified employee model
- precomputed risk snapshots (batch refresh)
- paginated risk insights
- nudge engine
- ONA analytics
- hiring simulation
- policy assistant

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

Refresh risk snapshots (batch mode):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/insights/refresh-risk-snapshots?batch_size=5000" \
  -H "X-API-Key: <key-if-enabled>"
```

## Checks

```bash
python -m ruff check .
python -m pytest -q
```
