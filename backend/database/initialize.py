from backend.config import settings
from backend.database.migrations.runner import run_migrations


def main() -> None:
    settings.paths.initialize()
    run_migrations()
    print(f"Database initialized at {settings.database_path}")


if __name__ == "__main__":
    main()
