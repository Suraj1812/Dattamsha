from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.database import engine


def main() -> None:
    settings = get_settings()

    print(f"Environment: {settings.environment}")
    print(f"Docs enabled: {settings.enable_docs}")
    print(f"API key required: {settings.require_api_key}")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connectivity: OK")
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database connectivity failed: {exc}") from exc

    print("Preflight checks passed")


if __name__ == "__main__":
    main()
