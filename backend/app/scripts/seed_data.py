from app.db.database import SessionLocal
from app.db.init_db import init_db
from app.services.ingest import load_sample_data


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = load_sample_data(db, source="sample")
    print(
        "Loaded "
        f"source={result.source}, employees={result.employees_loaded}, "
        f"metrics={result.metrics_loaded}, snapshots={result.snapshots_refreshed or 0}"
    )


if __name__ == "__main__":
    main()
