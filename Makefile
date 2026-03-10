run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

seed:
	python -m app.scripts.seed_data

preflight:
	python -m app.scripts.preflight

test:
	pytest -q

lint:
	ruff check .
