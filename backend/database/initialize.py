from backend.config import settings
from backend.database.migrations.runner import run_migrations

def main() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True); run_migrations(); print(f"Database initialized at {settings.database_path}")
if __name__ == "__main__": main()
