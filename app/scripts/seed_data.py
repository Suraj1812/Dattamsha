from app.db.database import SessionLocal
from app.db.init_db import init_db
from app.services.ingest import load_sample_data


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = load_sample_data(db, source="sample")
    print(
        f"Loaded source={result.source}, employees={result.employees_loaded}, metrics={result.metrics_loaded}"
    )


if __name__ == "__main__":
    main()
