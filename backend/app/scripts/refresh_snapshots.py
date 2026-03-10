from app.core.config import get_settings
from app.db.database import SessionLocal
from app.services.risk_snapshot import refresh_risk_snapshots


def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        processed = refresh_risk_snapshots(
            db,
            batch_size=settings.snapshot_refresh_batch_size,
        )
    print(f"Refreshed risk snapshots for employees={processed}")


if __name__ == "__main__":
    main()
