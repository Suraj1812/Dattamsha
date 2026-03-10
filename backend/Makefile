run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

refresh-snapshots:
	python -m app.scripts.refresh_snapshots

preflight:
	python -m app.scripts.preflight

test:
	pytest -q

lint:
	ruff check .
