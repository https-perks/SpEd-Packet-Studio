from collections.abc import Callable
from sqlalchemy import Connection, text
from backend.config import settings
from backend.database.session import engine
from backend.database.migrations.versions.v0001_initial import upgrade as v0001_upgrade
from backend.database.migrations.versions.v0002_sprint_one import upgrade as v0002_upgrade
from backend.database.migrations.versions.v0003_goal_summary import upgrade as v0003_upgrade
from backend.database.migrations.versions.v0004_case_manager_contact import upgrade as v0004_upgrade
from datetime import datetime, timezone
import shutil
import sqlite3
Migration = tuple[str, Callable[[Connection], None]]
MIGRATIONS: tuple[Migration, ...] = (
    ("0001_initial", v0001_upgrade),
    ("0002_sprint_one", v0002_upgrade),
    ("0003_goal_summary", v0003_upgrade),
    ("0004_case_manager_contact", v0004_upgrade),
)

def run_migrations() -> None:
    existing_applied: set[str] = set()
    if settings.database_path.exists() and settings.database_path.stat().st_size:
        try:
            with sqlite3.connect(settings.database_path) as database:
                table = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
                if table:
                    existing_applied = {row[0] for row in database.execute("SELECT version FROM schema_migrations")}
        except sqlite3.Error as error:
            raise RuntimeError(f"Cannot inspect application database before migration: {error}") from error
        pending = [version for version, _ in MIGRATIONS if version not in existing_applied]
        if pending:
            settings.backups_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(settings.database_path, settings.backups_dir / f"packet-studio-before-{'-'.join(pending)}-{stamp}.sqlite3")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(64) PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
        for version, upgrade in MIGRATIONS:
            if version not in applied:
                upgrade(connection)
                connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
        connection.execute(text("INSERT INTO settings (id, key, value_json, created_at, updated_at) VALUES ('schema-version', 'database.schema_version', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP"), {"value": f'"{settings.schema_version}"'})
